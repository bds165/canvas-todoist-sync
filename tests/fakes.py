"""In-memory fakes for the sync engine's two collaborators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from canvas_todoist.models import Assignment


class FakeCanvasSource:
    def __init__(self, assignments: list[Assignment] | None = None) -> None:
        self.assignments = list(assignments or [])

    def list_assignments(self) -> list[Assignment]:
        return list(self.assignments)


@dataclass
class FakeTask:
    id: str
    content: str
    description: str
    project_id: str
    section_id: str | None
    due: date | datetime


class FakeTodoist:
    """Keeps projects, sections and tasks in memory and records every write."""

    def __init__(self) -> None:
        self.projects: dict[str, str] = {}  # id -> name
        self.sections: dict[str, tuple[str, str]] = {}  # id -> (project_id, name)
        self.tasks: dict[str, FakeTask] = {}
        self.writes: list[tuple[str, object]] = []
        self._next_id = 1
        self.fail_creates_after: int | None = None  # simulate Todoist failing mid-run

    def _new_id(self) -> str:
        new_id = f"id{self._next_id}"
        self._next_id += 1
        return new_id

    # -- gateway --------------------------------------------------------

    def find_project(self, name: str) -> str | None:
        return next((pid for pid, n in self.projects.items() if n == name), None)

    def create_project(self, name: str) -> str:
        pid = self._new_id()
        self.projects[pid] = name
        self.writes.append(("create_project", name))
        return pid

    def list_sections(self, project_id: str) -> dict[str, str]:
        return {sid: name for sid, (pid, name) in self.sections.items() if pid == project_id}

    def create_section(self, project_id: str, name: str) -> str:
        sid = self._new_id()
        self.sections[sid] = (project_id, name)
        self.writes.append(("create_section", name))
        return sid

    def create_task(
        self,
        *,
        content: str,
        description: str,
        project_id: str,
        section_id: str | None,
        due: date | datetime,
    ) -> str:
        if self.fail_creates_after is not None and len(self.tasks) >= self.fail_creates_after:
            raise RuntimeError("Todoist unavailable")
        tid = self._new_id()
        self.tasks[tid] = FakeTask(tid, content, description, project_id, section_id, due)
        self.writes.append(("create_task", content))
        return tid

    # -- test helpers ---------------------------------------------------

    def task_titled(self, content: str) -> FakeTask:
        matches = [t for t in self.tasks.values() if t.content == content]
        assert len(matches) == 1, f"expected one task titled {content!r}, found {len(matches)}"
        return matches[0]

    def section_name(self, section_id: str | None) -> str:
        assert section_id is not None
        return self.sections[section_id][1]
