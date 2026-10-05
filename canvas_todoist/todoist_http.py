"""Todoist gateway over Todoist API v1 with plain HTTP. The token never appears in errors."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Protocol

from canvas_todoist.models import CanvasDueDate, format_utc

API = "https://api.todoist.com/api/v1"


class TodoistError(Exception):
    """Todoist rejected or failed a request."""


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
    def __init__(self, token: str, session: HttpSession) -> None:
        self._headers = {"Authorization": f"Bearer {token}"}
        self._session = session

    def find_project(self, name: str) -> str | None:
        return next((str(p["id"]) for p in self._list("/projects") if p["name"] == name), None)

    def create_project(self, name: str) -> str:
        return str(self._call("POST", "/projects", json={"name": name})["id"])

    def list_sections(self, project_id: str) -> dict[str, str]:
        return {str(s["id"]): s["name"] for s in self._list("/sections", {"project_id": project_id})}

    def create_section(self, project_id: str, name: str) -> str:
        return str(self._call("POST", "/sections", json={"name": name, "project_id": project_id})["id"])

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
        return str(self._call("POST", "/tasks", json=payload)["id"])

    def _list(self, path: str, params: dict[str, str] | None = None) -> Iterator[dict[str, Any]]:
        """Every item of a paginated v1 list endpoint."""
        params = dict(params or {}, limit="200")
        while True:
            page = self._call("GET", path, params=params)
            yield from page["results"]
            if not page.get("next_cursor"):
                return
            params["cursor"] = page["next_cursor"]

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._session.request(
                method, API + path, headers=self._headers, params=params, json=json, timeout=30
            )
        except Exception as exc:
            raise TodoistError(f"Todoist {method} {path} failed: {type(exc).__name__}") from None
        if not 200 <= response.status_code < 300:
            raise TodoistError(f"Todoist {method} {path} failed: HTTP {response.status_code}")
        return response.json()


def _due_fields(due: CanvasDueDate) -> dict[str, str]:
    if isinstance(due, datetime):
        return {"due_datetime": format_utc(due)}
    return {"due_date": due.isoformat()}
