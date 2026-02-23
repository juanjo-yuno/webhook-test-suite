from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class WebhookEvent:
    event_id: str
    payment_id: str
    event_type: str  # "payment.authorized", "payment.captured", etc.
    timestamp: datetime
    payload: dict
    signature: str = ""


@dataclass
class WebhookPayload:
    payment_id: str
    status: str
    amount: Decimal
    currency: str
    timestamp: str  # ISO 8601
    event_type: str
    authorization_code: str | None = None
    captured_amount: Decimal | None = None
    decline_code: str | None = None
    decline_message: str | None = None
    is_soft_decline: bool | None = None
    settlement_date: str | None = None
    settlement_amount: Decimal | None = None
    payout_currency: str | None = None
