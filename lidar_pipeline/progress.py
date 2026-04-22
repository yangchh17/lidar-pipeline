"""Real-time parser for R pipeline log output."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


# Patterns emitted by the R pipeline's futile.logger output
_RE_STEP = re.compile(r"Step (\d):")
_RE_TILE_PROGRESS = re.compile(r"(\d+)/(\d+)")
_RE_PIPELINE_DONE = re.compile(r"Pipeline complete \(([\d.]+) minutes\)")
_RE_ERROR = re.compile(r"^ERROR", re.IGNORECASE)
_RE_WARN = re.compile(r"^WARN", re.IGNORECASE)


@dataclass
class PipelineStatus:
    """Snapshot of pipeline progress."""

    current_step: int = 0
    total_steps: int = 5
    step_label: str = ""
    tiles_done: int = 0
    tiles_total: int = 0
    finished: bool = False
    elapsed_minutes: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def step_pct(self) -> float:
        if self.tiles_total == 0:
            return 0.0
        return self.tiles_done / self.tiles_total * 100

    @property
    def overall_pct(self) -> float:
        if self.total_steps == 0:
            return 0.0
        completed = max(0, self.current_step - 1)
        step_frac = self.step_pct / 100 if self.tiles_total else 0
        return (completed + step_frac) / self.total_steps * 100


STEP_LABELS = {
    1: "Filtering duplicates",
    2: "Ground classification + DTM",
    3: "DSM generation",
    4: "Hillshade",
    5: "QA report",
}


class LogParser:
    """Stateful parser that updates a PipelineStatus from R log lines."""

    def __init__(self, on_update: Optional[Callable[[PipelineStatus], None]] = None):
        self.status = PipelineStatus()
        self._on_update = on_update

    def feed(self, line: str) -> None:
        """Parse a single log line and update status."""
        line = line.strip()
        if not line:
            return

        step_match = _RE_STEP.search(line)
        if step_match:
            self.status.current_step = int(step_match.group(1))
            self.status.step_label = STEP_LABELS.get(
                self.status.current_step, f"Step {self.status.current_step}"
            )
            self.status.tiles_done = 0
            self.status.tiles_total = 0

        tile_match = _RE_TILE_PROGRESS.search(line)
        if tile_match:
            self.status.tiles_done = int(tile_match.group(1))
            self.status.tiles_total = int(tile_match.group(2))

        done_match = _RE_PIPELINE_DONE.search(line)
        if done_match:
            self.status.finished = True
            self.status.elapsed_minutes = float(done_match.group(1))

        if _RE_ERROR.match(line):
            self.status.errors.append(line)
        elif _RE_WARN.match(line):
            self.status.warnings.append(line)

        if self._on_update:
            self._on_update(self.status)
