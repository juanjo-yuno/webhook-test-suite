from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DeliveryStatus(Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


@dataclass
class DeliveryAttempt:
    attempt_id: str
    event_id: str
    url: str
    status_code: int | None
    timestamp: datetime
    response_time_ms: float
    error: str | None = None
