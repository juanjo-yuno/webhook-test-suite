import uuid
from datetime import datetime, timezone
from decimal import Decimal

from src.models.payment import Payment, PaymentStatus
from src.models.webhook import WebhookEvent, WebhookPayload


class PaymentFactory:
    """Factory for creating Payment instances with sensible defaults."""

    @staticmethod
    def create(**overrides) -> Payment:
        defaults = {
            "payment_id": f"pay_{uuid.uuid4().hex[:16]}",
            "amount": Decimal("100.00"),
            "currency": "USD",
            "status": PaymentStatus.AUTHORIZED,
            "merchant_id": f"merch_{uuid.uuid4().hex[:8]}",
            "created_at": datetime.now(timezone.utc),
            "metadata": {},
        }
        defaults.update(overrides)
        return Payment(**defaults)


class WebhookFactory:
    """Factory for creating WebhookEvent instances with sensible defaults."""

    @staticmethod
    def create_event(event_type: str = "payment.authorized", **overrides) -> WebhookEvent:
        payment_id = overrides.pop("payment_id", f"pay_{uuid.uuid4().hex[:16]}")
        now = datetime.now(timezone.utc)

        payload = WebhookFactory._build_payload(event_type, payment_id, now, **overrides)
        payload_overrides = overrides.pop("payload", None)
        if payload_overrides:
            payload.update(payload_overrides)

        defaults = {
            "event_id": f"evt_{uuid.uuid4().hex[:16]}",
            "payment_id": payment_id,
            "event_type": event_type,
            "timestamp": now,
            "payload": payload,
            "signature": "",
        }
        # Allow overriding top-level event fields
        for key in list(overrides):
            if key in defaults:
                defaults[key] = overrides.pop(key)

        return WebhookEvent(**defaults)

    @staticmethod
    def _build_payload(event_type: str, payment_id: str, timestamp: datetime, **kwargs) -> dict:
        base = {
            "payment_id": payment_id,
            "status": _event_type_to_status(event_type),
            "amount": str(kwargs.get("amount", "100.00")),
            "currency": kwargs.get("currency", "USD"),
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
        }

        if event_type == "payment.authorized":
            base["authorization_code"] = kwargs.get("authorization_code", "AUTH123456")
        elif event_type == "payment.captured":
            base["captured_amount"] = str(kwargs.get("captured_amount", base["amount"]))
        elif event_type == "payment.declined":
            base["decline_code"] = kwargs.get("decline_code", "insufficient_funds")
            base["decline_message"] = kwargs.get("decline_message", "Insufficient funds")
            base["is_soft_decline"] = kwargs.get("is_soft_decline", True)
        elif event_type == "payment.settled":
            base["settlement_date"] = kwargs.get("settlement_date", timestamp.strftime("%Y-%m-%d"))
            base["settlement_amount"] = str(kwargs.get("settlement_amount", base["amount"]))
            base["payout_currency"] = kwargs.get("payout_currency", base["currency"])
        elif event_type == "payment.chargeback":
            base["decline_code"] = kwargs.get("decline_code", "chargeback")
            base["decline_message"] = kwargs.get("decline_message", "Chargeback initiated by cardholder")

        return base


def _event_type_to_status(event_type: str) -> str:
    mapping = {
        "payment.authorized": "AUTHORIZED",
        "payment.captured": "CAPTURED",
        "payment.declined": "DECLINED",
        "payment.settled": "SETTLED",
        "payment.chargeback": "CHARGEBACK",
    }
    return mapping.get(event_type, "UNKNOWN")
