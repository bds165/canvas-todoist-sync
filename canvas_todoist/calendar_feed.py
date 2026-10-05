"""Calendar Feed adapter: reads Assignments from the Canvas iCal feed (ADR 0002).

The feed address works like a password, so it never appears in logs or errors.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any, Protocol
from urllib.parse import parse_qs, urlsplit

import icalendar

from canvas_todoist.http import HttpError, send_with_retry
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

    @property
    def headers(self) -> Mapping[str, str]: ...

    def json(self) -> Any: ...


class HttpSession(Protocol):
    def get(self, url: str, /, *, timeout: float) -> _Response: ...


class CalendarFeedSource:
    def __init__(
        self, feed_url: str, session: HttpSession, *, sleep: Callable[[float], None] = time.sleep
    ) -> None:
        self._feed_url = feed_url
        self._session = session
        self._sleep = sleep

    def list_assignments(self) -> list[Assignment]:
        return parse_feed(self._fetch())

    def _fetch(self) -> bytes:
        try:
            response = send_with_retry(
                lambda: self._session.get(self._feed_url, timeout=30), "Calendar Feed fetch", sleep=self._sleep
            )
        except HttpError as exc:
            raise CalendarFeedError(str(exc)) from None
        if response.status_code != 200:
            raise CalendarFeedError(f"Calendar Feed fetch failed: HTTP {response.status_code}")
        return response.content


def parse_feed(raw: bytes) -> list[Assignment]:
    """The feed's Assignments. A body that isn't a calendar at all (say, a login page) fails the
    whole read, rather than looking like an empty feed in which every Assignment went missing."""
    try:
        calendar = icalendar.Calendar.from_ical(raw)
    except ValueError:
        calendar = None
    if calendar is None or calendar.name != "VCALENDAR":
        raise CalendarFeedError("Calendar Feed is not a calendar; was the feed address changed?")
    assignments = []
    for event in calendar.walk("VEVENT"):
        uid_match = _UID.match(str(event.get("UID", "")))
        if uid_match is None:
            continue
        try:
            assignment = _to_assignment(uid_match.group(1), event)
        except Exception as exc:
            log.warning(
                "Skipping Assignment %s: unreadable in the feed (%s)", uid_match.group(1), type(exc).__name__
            )
            continue
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


def _due(value: object) -> CanvasDueDate:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return value
    raise ValueError("DTSTART is not a date or date-time")
