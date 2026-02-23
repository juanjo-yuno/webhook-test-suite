import threading
import time


class MetricsCollector:
    """Collects and computes webhook delivery metrics with rolling windows."""

    def __init__(self, window_seconds: float = 300):
        self._window_seconds = window_seconds
        self._successes: list[float] = []  # timestamps
        self._failures: list[float] = []
        self._lock = threading.Lock()

    def record_success(self, event_type: str | None = None) -> None:
        with self._lock:
            self._successes.append(time.monotonic())

    def record_failure(self, event_type: str | None = None) -> None:
        with self._lock:
            self._failures.append(time.monotonic())

    def _prune(self, data: list[float], now: float) -> list[float]:
        cutoff = now - self._window_seconds
        return [t for t in data if t >= cutoff]

    def failure_rate(self) -> float:
        """Failure rate in the current rolling window (0.0 to 1.0)."""
        with self._lock:
            now = time.monotonic()
            successes = self._prune(self._successes, now)
            failures = self._prune(self._failures, now)
            total = len(successes) + len(failures)
            if total == 0:
                return 0.0
            return len(failures) / total

    def total_in_window(self) -> int:
        with self._lock:
            now = time.monotonic()
            successes = self._prune(self._successes, now)
            failures = self._prune(self._failures, now)
            return len(successes) + len(failures)

    def failure_count_in_window(self) -> int:
        with self._lock:
            now = time.monotonic()
            return len(self._prune(self._failures, now))

    def success_count_in_window(self) -> int:
        with self._lock:
            now = time.monotonic()
            return len(self._prune(self._successes, now))

    def reset(self) -> None:
        with self._lock:
            self._successes.clear()
            self._failures.clear()
