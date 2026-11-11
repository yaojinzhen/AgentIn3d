"""Bounded runtime telemetry for Blender asset execution.

The recorder deliberately uses monotonic wall time and operating-system peak
working-set counters.  It has no dependency on Blender, so its accounting and
serialization contracts can be regression tested with ordinary Python.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from collections.abc import Iterator
from typing import Any, Callable

Clock = Callable[[], float]


def peak_rss_bytes() -> int | None:
    """Return the process peak resident set size in bytes when available."""

    if os.name == "nt":
        try:
            import psutil

            memory = psutil.Process().memory_info()
            return int(getattr(memory, "peak_wset", memory.rss))
        except (ImportError, AttributeError, OSError, TypeError, ValueError):
            return None

    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux and the BSDs report KiB; macOS reports bytes.
        return value if sys.platform == "darwin" else value * 1024
    except (ImportError, OSError, TypeError, ValueError):
        return None


class TelemetryRecorder:
    """Accumulate named phase durations and close the total-time equation."""

    def __init__(self, *, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self._phases: dict[str, float] = {}

    @contextlib.contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Measure one phase, accumulating repeated calls under the same key."""

        started = self._clock()
        try:
            yield
        finally:
            self.add(name, self._clock() - started)

    def add(self, name: str, seconds: float) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("telemetry phase name must be non-empty")
        value = max(0.0, float(seconds))
        self._phases[name] = self._phases.get(name, 0.0) + value

    def snapshot(
        self,
        *,
        object_count: int = 0,
        face_count: int = 0,
        vertex_count: int = 0,
        artifact_bytes: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        total = max(0.0, self._clock() - self._started)
        accounted = sum(self._phases.values())
        unattributed = max(0.0, total - accounted)
        return {
            "schema_version": "1.1",
            "clock": "monotonic_wall",
            "phases_seconds": {
                name: round(value, 6)
                for name, value in sorted(self._phases.items())
            },
            "accounted_seconds": round(accounted, 6),
            "unattributed_seconds": round(unattributed, 6),
            "total_seconds": round(total, 6),
            "closure_error_seconds": round(total - accounted - unattributed, 9),
            "peak_rss_bytes": peak_rss_bytes(),
            "complexity": {
                "object_count": max(0, int(object_count)),
                "evaluated_face_count": max(0, int(face_count)),
                "evaluated_vertex_count": max(0, int(vertex_count)),
            },
            "artifact_bytes": {
                name: max(0, int(size))
                for name, size in sorted((artifact_bytes or {}).items())
            },
        }
