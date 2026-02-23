from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class PaymentStatus(Enum):
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    DECLINED = "DECLINED"
    SETTLED = "SETTLED"
    CHARGEBACK = "CHARGEBACK"


@dataclass
class Payment:
    payment_id: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    merchant_id: str
    created_at: datetime
    metadata: dict = field(default_factory=dict)
