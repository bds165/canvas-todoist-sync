from __future__ import annotations

from typing import Protocol

from canvas_todoist.models import CanvasDueDate


class TodoistGateway(Protocol):
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
