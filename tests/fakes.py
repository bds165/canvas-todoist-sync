"""In-memory fakes for the sync engine's two collaborators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from canvas_todoist.models import Assignment
from canvas_todoist.todoist import TodoistTask


class FakeCanvasSource:
    def __init__(self, assignments: list[Assignment] | None = None) -> None:
        self.assignments = list(assignments or [])
        self.error: Exception | None = None  # simulate an unreachable or unreadable feed

    def list_assignments(self) -> list[Assignment]:
        if self.error is not None:
            raise self.error
        return list(self.assignments)


@dataclass
class FakeTask:
    id: str
    content: str
    description: str
    project_id: str
    section_id: str | None
    due: date | datetime
    completed_at: datetime | None = None

    def view(self) -> TodoistTask:
        return TodoistTask(self.id, self.project_id, self.description)


class FakeTodoist:
    """Keeps projects, sections and tasks in memory and records every write."""

    def __init__(self) -> None:
        self.projects: dict[str, str] = {}  # id -> name
        self.sections: dict[str, tuple[str, str]] = {}  # id -> (project_id, name)
        self.tasks: dict[str, FakeTask] = {}  # active tasks
        self.completed: dict[str, FakeTask] = {}
        self.writes: list[tuple[str, object]] = []
        self._next_id = 1
        # Simulate Todoist failing. Keys: "create_task:<title>", "create_section:<name>",
        # "update_task:<task id>", or "*" for every call (e.g. a rejected token).
        self.failures: dict[str, Exception] = {}

    def _new_id(self) -> str:
        new_id = f"id{self._next_id}"
        self._next_id += 1
        return new_id

    def _maybe_fail(self, operation: str, key: str = "") -> None:
        error = self.failures.get("*") or self.failures.get(f"{operation}:{key}")
        if error is not None:
            raise error

    # -- gateway --------------------------------------------------------

    def find_project(self, name: str) -> str | None:
        self._maybe_fail("find_project")
        return next((pid for pid, n in self.projects.items() if n == name), None)

    def create_project(self, name: str) -> str:
        self._maybe_fail("create_project")
        pid = self._new_id()
        self.projects[pid] = name
        self.writes.append(("create_project", name))
        return pid

    def list_sections(self, project_id: str) -> dict[str, str]:
        self._maybe_fail("list_sections")
        return {sid: name for sid, (pid, name) in self.sections.items() if pid == project_id}

    def create_section(self, project_id: str, name: str) -> str:
        self._maybe_fail("create_section", name)
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
        self._maybe_fail("create_task", content)
        tid = self._new_id()
        self.tasks[tid] = FakeTask(tid, content, description, project_id, section_id, due)
        self.writes.append(("create_task", content))
        return tid

    def list_active_tasks(self) -> list[TodoistTask]:
        self._maybe_fail("list_active_tasks")
        return [t.view() for t in self.tasks.values()]

    def list_completed_tasks(self, project_id: str, since: datetime, until: datetime) -> list[TodoistTask]:
        self._maybe_fail("list_completed_tasks")
        return [
            t.view() for t in self.completed.values()
            if t.project_id == project_id and t.completed_at is not None and since <= t.completed_at < until
        ]

    def update_task(self, task_id: str, *, due: date | datetime, description: str) -> None:
        self._maybe_fail("update_task", task_id)
        task = self.tasks[task_id]
        task.due, task.description = due, description
        self.writes.append(("update_task", task_id))

    # -- what the user does in Todoist ----------------------------------

    def complete(self, task_id: str, at: datetime) -> None:
        task = self.tasks.pop(task_id)
        task.completed_at = at
        self.completed[task_id] = task

    def delete(self, task_id: str) -> None:
        del self.tasks[task_id]

    def reschedule(self, task_id: str, due: date | datetime) -> None:
        self.tasks[task_id].due = due

    def move(self, task_id: str, project_id: str, section_id: str | None = None) -> None:
        task = self.tasks[task_id]
        task.project_id, task.section_id = project_id, section_id

    def delete_section(self, section_id: str | None) -> None:
        """As in Todoist, deleting a section deletes its tasks too."""
        del self.sections[section_id]
        self.tasks = {tid: t for tid, t in self.tasks.items() if t.section_id != section_id}

    def rename_section(self, section_id: str, name: str) -> None:
        project_id, _ = self.sections[section_id]
        self.sections[section_id] = (project_id, name)

    def add_task(self, content: str, description: str, project_id: str, due: date | datetime) -> str:
        """A task that exists in Todoist without this run having created it."""
        tid = self._new_id()
        self.tasks[tid] = FakeTask(tid, content, description, project_id, None, due)
        return tid

    # -- test helpers ---------------------------------------------------

    def task_titled(self, content: str) -> FakeTask:
        matches = [t for t in self.tasks.values() if t.content == content]
        assert len(matches) == 1, f"expected one task titled {content!r}, found {len(matches)}"
        return matches[0]

    def section_name(self, section_id: str | None) -> str:
        assert section_id is not None
        return self.sections[section_id][1]
