from __future__ import annotations

from typing import Protocol

from canvas_todoist.models import Assignment


class CanvasSource(Protocol):
    def list_assignments(self) -> list[Assignment]:
        """Every Assignment currently in the Calendar Feed."""
        ...
