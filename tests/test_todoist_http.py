from datetime import date, datetime, timezone

import pytest

from canvas_todoist.todoist_http import TodoistError, TodoistHttpGateway

TOKEN = "SECRETtodoistTOKEN"
API = "https://api.todoist.com/api/v1"


class CannedResponse:
    def __init__(self, status_code: int, body: object = None) -> None:
        self.status_code = status_code
        self._body = body
        self.text = "" if body is None else str(body)

    def json(self) -> object:
        return self._body


class CannedSession:
    def __init__(self, *responses: CannedResponse) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def request(self, method, url, *, headers, params=None, json=None, timeout):
        self.requests.append({"method": method, "url": url, "headers": headers, "params": params, "json": json})
        return self.responses.pop(0)


def gateway(*responses: CannedResponse) -> tuple[TodoistHttpGateway, CannedSession]:
    session = CannedSession(*responses)
    return TodoistHttpGateway(TOKEN, session), session


def create_task(gw: TodoistHttpGateway, due) -> str:
    return gw.create_task(content="Essay 1", description="https://x/courses/1/assignments/2",
                          project_id="p1", section_id="s1", due=due)


def test_timed_due_date_is_sent_as_fixed_utc_datetime():
    gw, session = gateway(CannedResponse(200, {"id": "t1"}))

    task_id = create_task(gw, datetime(2026, 10, 10, 10, 59, tzinfo=timezone.utc))

    sent = session.requests[0]
    assert (sent["method"], sent["url"]) == ("POST", f"{API}/tasks")
    assert sent["json"] == {
        "content": "Essay 1",
        "description": "https://x/courses/1/assignments/2",
        "project_id": "p1",
        "section_id": "s1",
        "due_datetime": "2026-10-10T10:59:00Z",
    }
    assert sent["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert task_id == "t1"


def test_date_only_due_date_is_sent_as_plain_date():
    gw, session = gateway(CannedResponse(200, {"id": "t1"}))

    create_task(gw, date(2026, 10, 12))

    payload = session.requests[0]["json"]
    assert payload["due_date"] == "2026-10-12"
    assert "due_datetime" not in payload


def test_find_project_follows_pagination():
    gw, session = gateway(
        CannedResponse(200, {"results": [{"id": "p1", "name": "Inbox"}], "next_cursor": "c2"}),
        CannedResponse(200, {"results": [{"id": "p2", "name": "School"}], "next_cursor": None}),
    )

    assert gw.find_project("School") == "p2"
    assert session.requests[1]["params"]["cursor"] == "c2"


def test_find_project_returns_none_when_absent():
    gw, _ = gateway(CannedResponse(200, {"results": [], "next_cursor": None}))

    assert gw.find_project("School") is None


def test_sections_are_listed_and_created_in_the_project():
    gw, session = gateway(
        CannedResponse(200, {"results": [{"id": "s1", "name": "COMPSCI 101"}], "next_cursor": None}),
        CannedResponse(200, {"id": "s2", "name": "MATHS 108"}),
    )

    assert gw.list_sections("p1") == {"s1": "COMPSCI 101"}
    assert gw.create_section("p1", "MATHS 108") == "s2"
    assert session.requests[0]["params"]["project_id"] == "p1"
    assert session.requests[1]["json"] == {"name": "MATHS 108", "project_id": "p1"}


def test_failed_request_does_not_reveal_token(caplog):
    caplog.set_level("DEBUG")
    gw, _ = gateway(CannedResponse(401, "Unauthorized"))

    with pytest.raises(TodoistError) as raised:
        gw.find_project("School")

    assert "401" in str(raised.value)
    assert TOKEN not in str(raised.value)
    assert TOKEN not in caplog.text
