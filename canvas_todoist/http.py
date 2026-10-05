"""Shared HTTP helper: retries transient failures for the feed fetch and Todoist alike.

Requests here carry secrets (the feed address, the Todoist token), so nothing is logged
and failures are reported only by the caller's label and the exception type.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol, TypeVar

import requests

ATTEMPTS = 4
BACKOFF = 1.0  # seconds before the first retry; doubles each time
MAX_WAIT = 60.0  # a rate limit asking for longer fails the request rather than stall the run


class HttpError(Exception):
    """A request could not be sent, even after retries."""


class Response(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    def json(self) -> Any: ...


R = TypeVar("R", bound=Response)


def send_with_retry(
    send: Callable[[], R],
    what: str,
    *,
    repeatable: bool = True,
    sleep: Callable[[float], None] = time.sleep,
) -> R:
    """Call `send`, retrying connection errors, timeouts, 429 and 5xx with backoff.

    A request that isn't `repeatable` (it creates something) is retried only on 429, which
    the server refused before acting; after any other failure it may have taken effect.
    Returns the last response, whatever its status, for the caller to judge.
    """
    for attempt in range(ATTEMPTS):
        last = attempt == ATTEMPTS - 1
        try:
            response = send()
        except Exception as exc:
            if repeatable and not last and isinstance(exc, (requests.ConnectionError, requests.Timeout)):
                sleep(BACKOFF * 2**attempt)
                continue
            # Request exceptions quote the URL, so report only the exception type.
            raise HttpError(f"{what} failed: {type(exc).__name__}") from None
        status = response.status_code
        retryable = status == 429 or (repeatable and 500 <= status < 600)
        if last or not retryable:
            return response
        wait = _retry_after(response) or BACKOFF * 2**attempt
        if wait > MAX_WAIT:
            return response
        sleep(wait)
    raise AssertionError("unreachable")


def _retry_after(response: Response) -> float | None:
    """Todoist's `error_extra.retry_after`, else a numeric Retry-After header."""
    try:
        return float(response.json()["error_extra"]["retry_after"])
    except Exception:
        pass
    try:
        return float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None
