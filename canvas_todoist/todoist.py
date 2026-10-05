from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from canvas_todoist.models import CanvasDueDate


class TodoistError(Exception):
    """Todoist rejected or failed a request."""


class PlanLimitReached(TodoistError):
    """A free-plan limit (sections, active tasks) stopped Todoist creating something."""


class TodoistRejectedToken(TodoistError):
    """Todoist doesn't accept the token, so no request can succeed."""


@dataclass(frozen=True)
class TodoistTask:
    """What the sync reads back about a Todoist task."""

    id: str
    project_id: str
    description: str


class TodoistGateway(Protocol):
    """Todoist as the sync sees it. There is no close operation: the sync never closes tasks.

    Creates raise PlanLimitReached when a free-plan limit is hit; any call raises
    TodoistRejectedToken when the token is refused.
    """

    def find_project(self, name: str) -> str | None: ...

    def create_project(self, name: str) -> str: ...

    def list_sections(self, project_id: str) -> dict[str, str]:
        """Section ID -> name for every section in the project."""
        ...

    def create_section(self, project_id: str, name: str) -> str: ...

    def create_task(
        self,
        *,
        content: str,
        description: str,
        project_id: str,
        section_id: str | None,
        due: CanvasDueDate,
    ) -> str: ...

    def list_active_tasks(self) -> list[TodoistTask]:
        """Every active task, across all projects."""
        ...

    def list_completed_tasks(self, project_id: str, since: datetime, until: datetime) -> list[TodoistTask]:
        """Tasks in the project completed in [since, until); Todoist allows at most 3 months."""
        ...

    def update_task(self, task_id: str, *, due: CanvasDueDate, description: str) -> None: ...
