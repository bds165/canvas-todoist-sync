"""The sync engine: all sync behaviour behind one entry point, run_sync."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from canvas_todoist.canvas import CanvasSource
from canvas_todoist.config import Config
from canvas_todoist.models import Assignment
from canvas_todoist.state import AssignmentState, CourseState, State
from canvas_todoist.todoist import TodoistGateway

log = logging.getLogger(__name__)


@dataclass
class Summary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0

    def __str__(self) -> str:
        return (
            f"created {self.created}, updated {self.updated}, "
            f"skipped {self.skipped}, errors {self.errors}"
        )


@dataclass
class RunResult:
    state: State
    summary: Summary


class SyncAborted(Exception):
    """The run failed partway. `result` still records every Synced Task created before that."""

    def __init__(self, result: RunResult) -> None:
        super().__init__(str(result.summary))
        self.result = result


def run_sync(
    canvas: CanvasSource,
    todoist: TodoistGateway,
    state: State | None,
    config: Config,
    now: datetime,
) -> RunResult:
    new_state = copy.deepcopy(state) if state is not None else State()
    run = _SyncRun(todoist, new_state, config)
    try:
        for assignment in canvas.list_assignments():
            if assignment.assignment_id in new_state.assignments:
                continue
            allowed = not config.course_allowlist or assignment.course_id in config.course_allowlist
            if not allowed or not _in_sync_window(assignment, config, now):
                run.summary.skipped += 1
                continue
            run.create(assignment)
    except Exception as exc:
        raise SyncAborted(RunResult(new_state, run.summary)) from exc
    return RunResult(new_state, run.summary)


def _in_sync_window(assignment: Assignment, config: Config, now: datetime) -> bool:
    """Timed due dates are compared to the moment; date-only ones as whole local days."""
    lookback = timedelta(days=config.lookback_days)
    lookahead = timedelta(days=config.lookahead_days)
    if isinstance(assignment.due, datetime):
        return now - lookback <= assignment.due <= now + lookahead
    today = now.astimezone(config.timezone).date()
    return today - lookback <= assignment.due <= today + lookahead


class _SyncRun:
    """One run's Todoist lookups (cached) and summary; records each write in the state as it happens."""

    def __init__(self, todoist: TodoistGateway, state: State, config: Config) -> None:
        self.todoist = todoist
        self.state = state
        self.config = config
        self.summary = Summary()
        self._project_id: str | None = None
        self._sections: dict[str, str] | None = None

    def project_id(self) -> str:
        if self._project_id is None:
            name = self.config.todoist_project_name
            self._project_id = self.todoist.find_project(name) or self.todoist.create_project(name)
        return self._project_id

    def sections(self) -> dict[str, str]:
        if self._sections is None:
            self._sections = self.todoist.list_sections(self.project_id())
        return self._sections

    def section_name(self, assignment: Assignment) -> str:
        return self.config.course_name_overrides.get(assignment.course_id, assignment.course_code)

    def section_id(self, assignment: Assignment) -> str:
        """The Course Section for the Assignment's course: stored, else found by name, else created."""
        stored = self.state.courses.get(assignment.course_id)
        if stored is not None and stored.section_id in self.sections():
            return stored.section_id
        name = self.section_name(assignment)
        section_id = next((sid for sid, n in self.sections().items() if n == name), None)
        if section_id is None:
            section_id = self.todoist.create_section(self.project_id(), name)
            self.sections()[section_id] = name
        self.state.courses[assignment.course_id] = CourseState(section_id)
        return section_id

    def create(self, assignment: Assignment) -> None:
        if self.config.dry_run:
            log.info(
                "Dry run: would create %r in %s, due %s",
                assignment.title, self.section_name(assignment), assignment.due.isoformat(),
            )
            self.summary.created += 1
            return
        task_id = self.todoist.create_task(
            content=assignment.title,
            description=assignment.url,
            project_id=self.project_id(),
            section_id=self.section_id(assignment),
            due=assignment.due,
        )
        self.state.assignments[assignment.assignment_id] = AssignmentState(task_id, assignment.due)
        self.summary.created += 1
        log.info("Created %r in %s", assignment.title, self.section_name(assignment))
