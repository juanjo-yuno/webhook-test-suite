import pytest
from datetime import datetime

from src.utils.factories import WebhookFactory


class TestAuthorizationPayload:
    """Tests for payment.authorized webhook payloads."""

    @pytest.mark.unit
    def test_authorization_payload_has_authorization_code(self):
        event = WebhookFactory.create_event("payment.authorized")
        assert "authorization_code" in event.payload
        assert event.payload["authorization_code"] == "AUTH123456"


class TestCapturePayload:
    """Tests for payment.captured webhook payloads."""

    @pytest.mark.unit
    def test_capture_payload_has_captured_amount(self):
        event = WebhookFactory.create_event("payment.captured")
        assert "captured_amount" in event.payload


class TestDeclinePayload:
    """Tests for payment.declined webhook payloads."""

    @pytest.mark.unit
    def test_decline_payload_has_decline_fields(self):
        event = WebhookFactory.create_event("payment.declined")
        assert "decline_code" in event.payload
        assert "decline_message" in event.payload
        assert "is_soft_decline" in event.payload
        assert event.payload["decline_code"] == "insufficient_funds"
        assert event.payload["decline_message"] == "Insufficient funds"
        assert event.payload["is_soft_decline"] is True


class TestSettlementPayload:
    """Tests for payment.settled webhook payloads."""

    @pytest.mark.unit
    def test_settlement_payload_has_settlement_fields(self):
        event = WebhookFactory.create_event("payment.settled")
        assert "settlement_date" in event.payload
        assert "settlement_amount" in event.payload
        assert "payout_currency" in event.payload


class TestChargebackPayload:
    """Tests for payment.chargeback webhook payloads."""

    @pytest.mark.unit
    def test_chargeback_payload_has_decline_code_and_message(self):
        event = WebhookFactory.create_event("payment.chargeback")
        assert "decline_code" in event.payload
        assert "decline_message" in event.payload
        assert event.payload["decline_code"] == "chargeback"


class TestEventTypeStatus:
    """Tests that event types map to correct status strings."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "event_type,expected_status",
        [
            ("payment.authorized", "AUTHORIZED"),
            ("payment.captured", "CAPTURED"),
            ("payment.declined", "DECLINED"),
            ("payment.settled", "SETTLED"),
            ("payment.chargeback", "CHARGEBACK"),
        ],
    )
    def test_all_event_types_set_correct_status(self, event_type, expected_status):
        event = WebhookFactory.create_event(event_type)
        assert event.payload["status"] == expected_status


class TestTimestamp:
    """Tests for timestamp format in payloads."""

    @pytest.mark.unit
    def test_timestamp_is_iso_8601(self):
        event = WebhookFactory.create_event("payment.authorized")
        ts = event.payload["timestamp"]
        # Should parse as ISO 8601 without raising
        parsed = datetime.fromisoformat(ts)
        assert isinstance(parsed, datetime)


class TestCurrencyAndAmounts:
    """Tests for currency and amount handling."""

    @pytest.mark.unit
    def test_multi_currency_support(self):
        for currency in ["USD", "EUR", "BRL", "COP"]:
            event = WebhookFactory.create_event("payment.authorized", currency=currency)
            assert event.payload["currency"] == currency

    @pytest.mark.unit
    def test_partial_capture(self):
        event = WebhookFactory.create_event(
            "payment.captured", amount="200.00", captured_amount="150.00"
        )
        assert event.payload["amount"] == "200.00"
        assert event.payload["captured_amount"] == "150.00"

    @pytest.mark.unit
    def test_default_amount_is_100(self):
        event = WebhookFactory.create_event("payment.authorized")
        assert event.payload["amount"] == "100.00"

    @pytest.mark.unit
    def test_default_currency_is_usd(self):
        event = WebhookFactory.create_event("payment.authorized")
        assert event.payload["currency"] == "USD"

    @pytest.mark.unit
    def test_custom_overrides_work(self):
        event = WebhookFactory.create_event(
            "payment.authorized",
            amount="500.00",
            currency="EUR",
            authorization_code="CUSTOM_AUTH",
        )
        assert event.payload["amount"] == "500.00"
        assert event.payload["currency"] == "EUR"
        assert event.payload["authorization_code"] == "CUSTOM_AUTH"
