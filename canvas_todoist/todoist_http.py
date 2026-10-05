"""Todoist gateway over Todoist API v1 with plain HTTP. The token never appears in errors."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any, Protocol

from canvas_todoist.http import HttpError, send_with_retry
from canvas_todoist.models import CanvasDueDate, format_utc
from canvas_todoist.todoist import PlanLimitReached, TodoistError, TodoistRejectedToken, TodoistTask

API = "https://api.todoist.com/api/v1"


class HttpSession(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float,
    ) -> Any: ...


class TodoistHttpGateway:
    def __init__(self, token: str, session: HttpSession, *, sleep: Callable[[float], None] = time.sleep) -> None:
        self._headers = {"Authorization": f"Bearer {token}"}
        self._session = session
        self._sleep = sleep

    def find_project(self, name: str) -> str | None:
        return next((str(p["id"]) for p in self._list("/projects") if p["name"] == name), None)

    def create_project(self, name: str) -> str:
        return str(self._create("/projects", {"name": name})["id"])

    def list_sections(self, project_id: str) -> dict[str, str]:
        return {str(s["id"]): s["name"] for s in self._list("/sections", {"project_id": project_id})}

    def create_section(self, project_id: str, name: str) -> str:
        return str(self._create("/sections", {"name": name, "project_id": project_id})["id"])

    def create_task(
        self,
        *,
        content: str,
        description: str,
        project_id: str,
        section_id: str | None,
        due: CanvasDueDate,
    ) -> str:
        payload: dict[str, Any] = {
            "content": content,
            "description": description,
            "project_id": project_id,
            "section_id": section_id,
        }
        payload.update(_due_fields(due))
        return str(self._create("/tasks", payload)["id"])

    def list_active_tasks(self) -> list[TodoistTask]:
        return [_task(t) for t in self._list("/tasks")]

    def list_completed_tasks(self, project_id: str, since: datetime, until: datetime) -> list[TodoistTask]:
        params = {"project_id": project_id, "since": format_utc(since), "until": format_utc(until)}
        return [_task(t) for t in self._list("/tasks/completed/by_completion_date", params, key="items")]

    def update_task(self, task_id: str, *, due: CanvasDueDate, description: str) -> None:
        self._call("POST", f"/tasks/{task_id}", json={"description": description, **_due_fields(due)})

    def _list(
        self, path: str, params: dict[str, str] | None = None, *, key: str = "results"
    ) -> Iterator[dict[str, Any]]:
        """Every item of a paginated v1 list endpoint."""
        params = dict(params or {}, limit="200")
        while True:
            page = self._call("GET", path, params=params)
            yield from page[key]
            if not page.get("next_cursor"):
                return
            params["cursor"] = page["next_cursor"]

    def _create(self, path: str, payload: dict[str, Any]) -> Any:
        """Todoist has no deduplication for creates, so they aren't retried where a retry could duplicate."""
        return self._call("POST", path, json=payload, repeatable=False)

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        repeatable: bool = True,
    ) -> Any:
        what = f"Todoist {method} {path}"
        try:
            response = send_with_retry(
                lambda: self._session.request(
                    method, API + path, headers=self._headers, params=params, json=json, timeout=30
                ),
                what,
                repeatable=repeatable,
                sleep=self._sleep,
            )
        except HttpError as exc:
            raise TodoistError(str(exc)) from None
        status = response.status_code
        if 200 <= status < 300:
            return response.json()
        failed = f"{what} failed: HTTP {status}"
        if status == 401:
            raise TodoistRejectedToken(failed)
        error_tag = _error_tag(response)
        if status != 429 and "LIMIT_REACHED" in error_tag:
            raise PlanLimitReached(f"{failed}, {error_tag}")
        raise TodoistError(failed)


def _error_tag(response: Any) -> str:
    """The error_tag of a Todoist error body, e.g. MAX_ITEMS_LIMIT_REACHED; "" if there is none."""
    try:
        return str(response.json()["error_tag"])
    except Exception:
        return ""


def _due_fields(due: CanvasDueDate) -> dict[str, str]:
    if isinstance(due, datetime):
        return {"due_datetime": format_utc(due)}
    return {"due_date": due.isoformat()}


def _task(raw: dict[str, Any]) -> TodoistTask:
    return TodoistTask(str(raw["id"]), str(raw["project_id"]), raw.get("description") or "")
