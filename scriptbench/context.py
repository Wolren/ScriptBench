"""
BenchmarkContext  --  passed to scripts that implement the optional run_benchmark(context) API.

Usage inside a benchmark-ready script:
    def run_benchmark(context):
        context.phase("setup")
        # ... setup code ...
        context.phase("compute")
        # ... heavy computation ...
        context.phase("save")
        # ... file writing (will be redirected to temp_dir) ...

SAVE_OUTPUT is also injected into the script namespace as a global.
"""

import time
from typing import Dict, List, Optional


class PhaseRecord:
    def __init__(self, name: str, start: float):
        self.name = name
        self.start = start
        self.end: Optional[float] = None

    def duration(self) -> float:
        if self.end is None:
            return 0.0
        return self.end - self.start


class BenchmarkContext:
    """
    Passed to run_benchmark(context). Tracks phase boundaries and timing.
    Also exposes output_dir and temp_dir so scripts can write without hardcoding.
    """

    def __init__(self, output_dir: str, temp_dir: str, save_output: bool = False):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        self.save_output = save_output

        self._phases: List[PhaseRecord] = []
        self._current: Optional[PhaseRecord] = None
        self._total_start: float = 0.0
        self._total_end: Optional[float] = None

    # -----------------------------------------------------------------
    # Public API for scripts
    # -----------------------------------------------------------------

    def phase(self, name: str) -> None:
        """Mark the start of a named phase. Automatically closes the previous one."""
        now = time.perf_counter()
        if self._current is not None:
            self._current.end = now
        record = PhaseRecord(name, now)
        self._phases.append(record)
        self._current = record

    # -----------------------------------------------------------------
    # Internal harness API
    # -----------------------------------------------------------------

    def _start(self) -> None:
        self._total_start = time.perf_counter()

    def _stop(self) -> None:
        now = time.perf_counter()
        if self._current is not None:
            self._current.end = now
        self._total_end = now

    def total_time(self) -> float:
        if self._total_end is None:
            return 0.0
        return self._total_end - self._total_start

    def phase_times(self) -> Dict[str, float]:
        """Returns {phase_name: seconds} for all completed phases."""
        result: Dict[str, float] = {}
        for p in self._phases:
            dur = p.duration()
            if p.name in result:
                result[p.name] += dur
            else:
                result[p.name] = dur
        return result

    def compute_time(self) -> Optional[float]:
        pt = self.phase_times()
        return pt.get("compute", None)

    def save_time(self) -> Optional[float]:
        pt = self.phase_times()
        return pt.get("save", None)

    def has_phases(self) -> bool:
        return len(self._phases) > 0
