import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import requests

from canvas_todoist.calendar_feed import CalendarFeedError, CalendarFeedSource

FEED_URL = "https://canvas.example.edu/feeds/calendars/user_SECRETfeedTOKEN.ics"
FIXTURE = (Path(__file__).parent / "fixtures" / "feed.ics").read_bytes()


class CannedResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content
        self.headers: dict[str, str] = {}

    def json(self) -> object:
        raise ValueError("not JSON")


class CannedSession:
    """Plays back responses, or raises exceptions, one request at a time."""

    def __init__(self, *responses: CannedResponse | Exception) -> None:
        self.responses = list(responses)
        self.requested: list[str] = []

    def get(self, url: str, timeout: float) -> CannedResponse:
        self.requested.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def source(*responses: CannedResponse | Exception) -> CalendarFeedSource:
    return CalendarFeedSource(FEED_URL, CannedSession(*responses), sleep=lambda _: None)


def feed_assignments():
    return {a.assignment_id: a for a in source(CannedResponse(200, FIXTURE)).list_assignments()}


def test_only_assignment_events_are_kept():
    assert set(feed_assignments()) == {"1001", "2002"}


def test_course_comes_from_event_link_and_title_tag():
    essay = feed_assignments()["1001"]
    assert (essay.course_id, essay.course_code) == ("77", "COMPSCI 101")


def test_title_is_unescaped_and_has_no_course_tag():
    assert feed_assignments()["1001"].title == "Essay 1: Algorithms, data and you"


def test_assignment_link_points_at_the_assignment():
    assert feed_assignments()["2002"].url == "https://canvas.example.edu/courses/88/assignments/2002"


def test_timed_event_is_utc_and_date_only_event_is_a_plain_date():
    assignments = feed_assignments()
    assert assignments["1001"].due == datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc)
    assert type(assignments["2002"].due) is date
    assert assignments["2002"].due == date(2026, 10, 12)


@pytest.mark.parametrize("failure", [CannedResponse(503), requests.ConnectionError(f"Max retries for {FEED_URL}")])
def test_failed_fetch_is_retried(failure):
    session = CannedSession(failure, CannedResponse(200, FIXTURE))

    assignments = CalendarFeedSource(FEED_URL, session, sleep=lambda _: None).list_assignments()

    assert len(assignments) == 2
    assert len(session.requested) == 2


@pytest.mark.parametrize(
    "failures",
    [
        [CannedResponse(404)],
        [CannedResponse(503)] * 4,
        [requests.ConnectionError(f"Max retries exceeded with url: {FEED_URL}")] * 4,
    ],
)
def test_failed_fetch_does_not_reveal_feed_address(caplog, failures):
    caplog.set_level(logging.DEBUG)

    with pytest.raises(CalendarFeedError) as raised:
        source(*failures).list_assignments()

    assert "SECRETfeedTOKEN" not in str(raised.value)
    assert "SECRETfeedTOKEN" not in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        b"<html><body>Please log in</body></html>",
        b"",
        b"BEGIN:VEVENT\r\nUID:event-assignment-1\r\nEND:VEVENT\r\n",
    ],
)
def test_feed_that_is_not_a_calendar_fails_clearly(body):
    with pytest.raises(CalendarFeedError, match="not a calendar"):
        source(CannedResponse(200, body)).list_assignments()


def test_one_unreadable_assignment_is_skipped_with_a_warning(caplog):
    body = FIXTURE.replace(b"DTSTART:20261010T105900Z", b"DTSTART:garbage")

    assignments = source(CannedResponse(200, body)).list_assignments()

    assert [a.assignment_id for a in assignments] == ["2002"]
    assert "1001" in caplog.text
