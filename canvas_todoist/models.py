from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

# A Canvas Due Date is either an aware UTC datetime or a plain date (date-only).
# Note that datetime is a subclass of date, so check for datetime first.
CanvasDueDate = date | datetime


@dataclass(frozen=True)
class Assignment:
    assignment_id: str
    course_id: str
    course_code: str
    title: str
    due: CanvasDueDate
    url: str


def format_utc(moment: datetime) -> str:
    """A fixed UTC timestamp, as Todoist and state.json both expect: 2026-10-10T10:59:00Z."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
