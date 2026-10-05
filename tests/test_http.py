import pytest
import requests

from canvas_todoist.http import HttpError, send_with_retry


class Canned:
    def __init__(self, status_code: int, body: object = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body

    def json(self) -> object:
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


class Sequence:
    """Plays back responses (or raises exceptions) one call at a time."""

    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self) -> Canned:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, Canned)
        return outcome


def run(*outcomes: object) -> tuple[Canned, Sequence, list[float]]:
    sleeps: list[float] = []
    sequence = Sequence(*outcomes)
    return send_with_retry(sequence, "Thing fetch", sleep=sleeps.append), sequence, sleeps


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_retries_on_rate_limit_and_server_errors_with_growing_backoff(status):
    response, sequence, sleeps = run(Canned(status), Canned(status), Canned(200))

    assert response.status_code == 200
    assert sequence.calls == 3
    assert len(sleeps) == 2 and 0 < sleeps[0] < sleeps[1]


def test_retries_on_connection_errors():
    response, sequence, _ = run(requests.ConnectionError("https://secret/url"), Canned(200))

    assert response.status_code == 200
    assert sequence.calls == 2


def test_client_errors_are_not_retried():
    response, sequence, sleeps = run(Canned(404))

    assert response.status_code == 404
    assert (sequence.calls, sleeps) == (1, [])


def test_returns_last_response_once_retries_run_out():
    response, sequence, sleeps = run(*[Canned(503)] * 4)

    assert response.status_code == 503
    assert sequence.calls == 4
    assert len(sleeps) == 3


def test_retry_after_in_todoist_error_body_is_honoured():
    _, _, sleeps = run(Canned(429, {"error_tag": "TOO_MANY_REQUESTS", "error_extra": {"retry_after": 13}}), Canned(200))

    assert sleeps == [13]


def test_retry_after_header_is_honoured():
    _, _, sleeps = run(Canned(429, headers={"Retry-After": "7"}), Canned(200))

    assert sleeps == [7]


def test_connection_error_that_persists_names_only_the_request_and_error_type():
    with pytest.raises(HttpError) as raised:
        run(*[requests.ConnectionError("https://canvas/feeds/SECRET.ics")] * 4)

    assert str(raised.value) == "Thing fetch failed: ConnectionError"
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_request_that_is_unsafe_to_repeat_is_retried_only_on_rate_limit():
    sleeps: list[float] = []

    server_error = send_with_retry(Sequence(Canned(503), Canned(200)), "Create", repeatable=False, sleep=sleeps.append)
    rate_limited = send_with_retry(Sequence(Canned(429), Canned(200)), "Create", repeatable=False, sleep=sleeps.append)

    assert server_error.status_code == 503
    assert rate_limited.status_code == 200


def test_request_that_is_unsafe_to_repeat_is_not_retried_after_a_timeout():
    sequence = Sequence(requests.ReadTimeout("read timed out"), Canned(200))

    with pytest.raises(HttpError, match="ReadTimeout"):
        send_with_retry(sequence, "Create", repeatable=False, sleep=lambda _: None)
    assert sequence.calls == 1


def test_retry_after_too_long_to_wait_for_gives_up():
    response, sequence, sleeps = run(Canned(429, headers={"Retry-After": "900"}), Canned(200))

    assert response.status_code == 429
    assert (sequence.calls, sleeps) == (1, [])


def test_errors_that_retrying_cannot_fix_are_not_retried():
    with pytest.raises(HttpError, match="InvalidURL"):
        run(requests.exceptions.InvalidURL("bad"), Canned(200))
