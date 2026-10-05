"""Sync state and the state store for state.json. State holds no secrets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, cast

from canvas_todoist.models import CanvasDueDate, format_utc

Status = Literal["open", "dismissed", "missing_from_canvas"]


@dataclass
class CourseState:
    section_id: str


@dataclass
class AssignmentState:
    task_id: str
    canvas_due: CanvasDueDate
    status: Status = "open"


@dataclass
class State:
    courses: dict[str, CourseState] = field(default_factory=dict)
    assignments: dict[str, AssignmentState] = field(default_factory=dict)


def load_state(path: Path) -> State | None:
    """The saved state, or None when the file is missing."""
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return State(
        courses={cid: CourseState(c["section_id"]) for cid, c in raw.get("courses", {}).items()},
        assignments={
            aid: AssignmentState(a["task_id"], _parse_due(a["canvas_due"]), cast(Status, a["status"]))
            for aid, a in raw.get("assignments", {}).items()
        },
    )


def save_state(path: Path, state: State) -> None:
    raw: dict[str, Any] = {
        "courses": {cid: {"section_id": c.section_id} for cid, c in state.courses.items()},
        "assignments": {
            aid: {"task_id": a.task_id, "canvas_due": _format_due(a.canvas_due), "status": a.status}
            for aid, a in state.assignments.items()
        },
    }
    path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_due(due: CanvasDueDate) -> str:
    if isinstance(due, datetime):
        return format_utc(due)
    return due.isoformat()


def _parse_due(value: str) -> CanvasDueDate:
    if "T" in value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return date.fromisoformat(value)
