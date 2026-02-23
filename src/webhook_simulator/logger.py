import threading
from datetime import datetime

from src.models.delivery import DeliveryAttempt


class DeliveryLogger:
    """Thread-safe logger for tracking webhook delivery attempts."""

    def __init__(self):
        self._attempts: list[DeliveryAttempt] = []
        self._lock = threading.Lock()

    def log(self, attempt: DeliveryAttempt) -> None:
        with self._lock:
            self._attempts.append(attempt)

    def get_attempts(self, event_id: str | None = None) -> list[DeliveryAttempt]:
        with self._lock:
            if event_id is None:
                return list(self._attempts)
            return [a for a in self._attempts if a.event_id == event_id]

    def get_failed_attempts(self) -> list[DeliveryAttempt]:
        with self._lock:
            return [
                a for a in self._attempts
                if a.status_code is None or a.status_code >= 400
            ]

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()
