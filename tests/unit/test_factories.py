import pytest
from decimal import Decimal

from src.models.payment import Payment, PaymentStatus
from src.utils.factories import PaymentFactory, WebhookFactory


class TestPaymentFactory:
    """Tests for PaymentFactory."""

    @pytest.mark.unit
    def test_create_returns_payment_with_defaults(self):
        payment = PaymentFactory.create()
        assert isinstance(payment, Payment)
        assert payment.amount == Decimal("100.00")
        assert payment.currency == "USD"
        assert payment.status == PaymentStatus.AUTHORIZED
        assert payment.payment_id.startswith("pay_")
        assert payment.merchant_id.startswith("merch_")
        assert payment.metadata == {}

    @pytest.mark.unit
    def test_create_with_custom_values(self):
        payment = PaymentFactory.create(
            amount=Decimal("250.00"),
            currency="EUR",
            status=PaymentStatus.CAPTURED,
        )
        assert payment.amount == Decimal("250.00")
        assert payment.currency == "EUR"
        assert payment.status == PaymentStatus.CAPTURED

    @pytest.mark.unit
    def test_create_generates_unique_ids(self):
        p1 = PaymentFactory.create()
        p2 = PaymentFactory.create()
        assert p1.payment_id != p2.payment_id
        assert p1.merchant_id != p2.merchant_id


class TestWebhookFactory:
    """Tests for WebhookFactory."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "event_type",
        [
            "payment.authorized",
            "payment.captured",
            "payment.declined",
            "payment.settled",
            "payment.chargeback",
        ],
    )
    def test_create_event_for_all_event_types(self, event_type):
        event = WebhookFactory.create_event(event_type)
        assert event.event_type == event_type
        assert event.payload["event_type"] == event_type
        assert event.event_id.startswith("evt_")
        assert event.payment_id.startswith("pay_")

    @pytest.mark.unit
    def test_create_event_custom_overrides(self):
        event = WebhookFactory.create_event(
            "payment.authorized",
            payment_id="pay_custom_123",
            amount="999.99",
            currency="BRL",
        )
        assert event.payment_id == "pay_custom_123"
        assert event.payload["payment_id"] == "pay_custom_123"
        assert event.payload["amount"] == "999.99"
        assert event.payload["currency"] == "BRL"

    @pytest.mark.unit
    def test_create_event_generates_unique_event_ids(self):
        e1 = WebhookFactory.create_event("payment.authorized")
        e2 = WebhookFactory.create_event("payment.authorized")
        assert e1.event_id != e2.event_id
