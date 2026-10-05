import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from canvas_todoist.calendar_feed import CalendarFeedError, CalendarFeedSource

FEED_URL = "https://canvas.example.edu/feeds/calendars/user_SECRETfeedTOKEN.ics"
FIXTURE = (Path(__file__).parent / "fixtures" / "feed.ics").read_bytes()


class CannedResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class CannedSession:
    def __init__(self, *responses: CannedResponse) -> None:
        self.responses = list(responses)
        self.requested: list[str] = []

    def get(self, url: str, timeout: float) -> CannedResponse:
        self.requested.append(url)
        return self.responses.pop(0)


def feed_assignments():
    source = CalendarFeedSource(FEED_URL, CannedSession(CannedResponse(200, FIXTURE)))
    return {a.assignment_id: a for a in source.list_assignments()}


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


def test_failed_fetch_does_not_reveal_feed_address(caplog):
    caplog.set_level(logging.DEBUG)
    source = CalendarFeedSource(FEED_URL, CannedSession(CannedResponse(404)))

    with pytest.raises(CalendarFeedError) as raised:
        source.list_assignments()

    assert "SECRETfeedTOKEN" not in str(raised.value)
    assert "SECRETfeedTOKEN" not in caplog.text
