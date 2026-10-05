"""The sync engine: all sync behaviour behind one entry point, run_sync."""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from canvas_todoist.canvas import CanvasSource
from canvas_todoist.config import Config
from canvas_todoist.models import Assignment, CanvasDueDate
from canvas_todoist.state import AssignmentState, CourseState, State, Status
from canvas_todoist.todoist import TodoistGateway, TodoistTask

log = logging.getLogger(__name__)

# Todoist lists completed tasks for at most 3 months; 89 days fits inside that in every month.
COMPLETED_HISTORY = timedelta(days=89)


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
    run = _SyncRun(todoist, new_state, config, now)
    try:
        active = {task.id: task for task in todoist.list_active_tasks()}
        assignments = canvas.list_assignments()
        if state is None:
            run.adopt_by_link(assignments, active)
        _detect_dismissed(new_state, active)
        for assignment in assignments:
            entry = new_state.assignments.get(assignment.assignment_id)
            if entry is not None:
                if entry.status == "missing_from_canvas":
                    _restore(assignment, entry)
                if entry.status == "open" and _changed(entry.canvas_due, assignment.due):
                    run.update_due(assignment, entry, active[entry.task_id])
                continue
            allowed = not config.course_allowlist or assignment.course_id in config.course_allowlist
            if not allowed or not _in_sync_window(assignment, config, now):
                run.summary.skipped += 1
                continue
            run.create(assignment)
        _detect_missing(new_state, {a.assignment_id for a in assignments})
    except Exception as exc:
        raise SyncAborted(RunResult(new_state, run.summary)) from exc
    return RunResult(new_state, run.summary)


def _detect_dismissed(state: State, active: dict[str, TodoistTask]) -> None:
    """A Synced Task no longer active anywhere was completed or deleted; either way it's Dismissed."""
    for assignment_id, entry in state.assignments.items():
        if entry.task_id in active:
            continue
        if entry.status == "open":
            entry.status = "dismissed"
        elif entry.status == "missing_from_canvas" and entry.previous_status == "open":
            entry.previous_status = "dismissed"
        else:
            continue
        log.info("Assignment %s is Dismissed: its task was completed or deleted", assignment_id)


def _detect_missing(state: State, in_feed: set[str]) -> None:
    """An open Assignment absent from the feed is left alone; logged only as it goes missing."""
    for assignment_id, entry in state.assignments.items():
        if entry.status == "open" and assignment_id not in in_feed:
            entry.previous_status, entry.status = entry.status, "missing_from_canvas"
            log.warning("Assignment %s is Missing from Canvas; leaving its task as it is", assignment_id)


def _restore(assignment: Assignment, entry: AssignmentState) -> None:
    entry.status, entry.previous_status = entry.previous_status or "open", None
    log.info("%r is back in Canvas", assignment.title)


def _changed(last_synced: CanvasDueDate, due: CanvasDueDate) -> bool:
    """A switch between date-only and timed counts as a change, even on the same day."""
    return type(last_synced) is not type(due) or last_synced != due


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

    def __init__(self, todoist: TodoistGateway, state: State, config: Config, now: datetime) -> None:
        self.todoist = todoist
        self.state = state
        self.config = config
        self.now = now
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

    def adopt_by_link(self, assignments: list[Assignment], active: dict[str, TodoistTask]) -> None:
        """Without state, find each Assignment's existing Synced Task by its link instead of duplicating it."""
        project_id = self.todoist.find_project(self.config.todoist_project_name)
        if project_id is None:
            return
        self._project_id = project_id
        school = [task for task in active.values() if task.project_id == project_id]
        completed = self.todoist.list_completed_tasks(project_id, self.now - COMPLETED_HISTORY, self.now)
        for assignment in assignments:
            # The link must end where the ID does: .../assignments/100 is not .../assignments/1001.
            link = re.compile(re.escape(assignment.url) + r"(?!\w)")
            status: Status
            for status, tasks in (("open", school), ("dismissed", completed)):
                if adopted := next((t for t in tasks if link.search(t.description)), None):
                    break
            else:
                continue
            self.state.assignments[assignment.assignment_id] = AssignmentState(adopted.id, assignment.due, status)
            log.info("Rebuilt state: %r is %s", assignment.title, status)

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

    def update_due(self, assignment: Assignment, entry: AssignmentState, task: TodoistTask) -> None:
        """Apply a new Canvas Due Date, noting it after whatever the description now says."""
        today = self.now.astimezone(self.config.timezone).date()
        note = f"Due date updated from Canvas on {today.isoformat()}"
        description = f"{task.description}\n\n{note}" if task.description else note
        if self.config.dry_run:
            log.info("Dry run: would update %r to be due %s", assignment.title, assignment.due.isoformat())
        else:
            self.todoist.update_task(entry.task_id, due=assignment.due, description=description)
            entry.canvas_due = assignment.due
            log.info("Due date of %r updated to %s", assignment.title, assignment.due.isoformat())
        self.summary.updated += 1
