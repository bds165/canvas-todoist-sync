"""Calendar Feed adapter: reads Assignments from the Canvas iCal feed (ADR 0002).

The feed address works like a password, so it never appears in logs or errors.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Protocol
from urllib.parse import parse_qs, urlsplit

import icalendar

from canvas_todoist.models import Assignment, CanvasDueDate

log = logging.getLogger(__name__)

_UID = re.compile(r"^event-assignment-(\d+)$")
_COURSE_CONTEXT = re.compile(r"^course_(\d+)$")
_COURSE_TAG = re.compile(r"\s*\[([^\[\]]+)\]\s*$")


class CalendarFeedError(Exception):
    """The Calendar Feed could not be fetched or read."""


class _Response(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def content(self) -> bytes: ...


class HttpSession(Protocol):
    def get(self, url: str, /, *, timeout: float) -> _Response: ...


class CalendarFeedSource:
    def __init__(self, feed_url: str, session: HttpSession) -> None:
        self._feed_url = feed_url
        self._session = session

    def list_assignments(self) -> list[Assignment]:
        return parse_feed(self._fetch())

    def _fetch(self) -> bytes:
        try:
            response = self._session.get(self._feed_url, timeout=30)
        except Exception as exc:
            # Request exceptions quote the URL, so report only the exception type.
            raise CalendarFeedError(f"Calendar Feed fetch failed: {type(exc).__name__}") from None
        if response.status_code != 200:
            raise CalendarFeedError(f"Calendar Feed fetch failed: HTTP {response.status_code}")
        return response.content


def parse_feed(raw: bytes) -> list[Assignment]:
    calendar = icalendar.Calendar.from_ical(raw)
    assignments = []
    for event in calendar.walk("VEVENT"):
        uid_match = _UID.match(str(event.get("UID", "")))
        if uid_match is None:
            continue
        assignment = _to_assignment(uid_match.group(1), event)
        if assignment is not None:
            assignments.append(assignment)
    return assignments


def _to_assignment(assignment_id: str, event: icalendar.cal.Component) -> Assignment | None:
    link = urlsplit(str(event.get("URL", "")))
    contexts = parse_qs(link.query).get("include_contexts", [])
    course_ids = [m.group(1) for c in contexts if (m := _COURSE_CONTEXT.match(c))]
    if not course_ids or "DTSTART" not in event:
        log.warning("Skipping Assignment %s: no course link or due date in the feed", assignment_id)
        return None
    course_id = course_ids[0]

    summary = str(event.get("SUMMARY", ""))
    tag = _COURSE_TAG.search(summary)
    title = summary[: tag.start()] if tag else summary
    course_code = tag.group(1).strip() if tag else f"Course {course_id}"

    return Assignment(
        assignment_id=assignment_id,
        course_id=course_id,
        course_code=course_code,
        title=title.strip(),
        due=_due(event.decoded("DTSTART")),
        url=f"{link.scheme}://{link.netloc}/courses/{course_id}/assignments/{assignment_id}",
    )


def _due(value: date | datetime) -> CanvasDueDate:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return value
