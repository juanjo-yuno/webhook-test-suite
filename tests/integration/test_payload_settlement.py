"""Integration tests for settlement webhook payload delivery."""

import re

import pytest

from src.utils.factories import WebhookFactory


pytestmark = pytest.mark.integration


class TestPayloadSettlement:
    """Test settlement event payload structure and delivery."""

    def test_settlement_has_required_fields(self, engine, merchant_server):
        """Settlement has settlement_date, settlement_amount, payout_currency."""
        event = WebhookFactory.create_event(event_type="payment.settled")
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 1
        payload = received[0]["payload"]

        assert "settlement_date" in payload
        assert "settlement_amount" in payload
        assert "payout_currency" in payload

    def test_fx_conversion(self, engine, merchant_server):
        """FX conversion: payout_currency != original currency, settlement_amount differs."""
        event = WebhookFactory.create_event(
            event_type="payment.settled",
            currency="USD",
            amount="100.00",
            payout_currency="EUR",
            settlement_amount="92.50",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        payload = received[0]["payload"]

        assert payload["payout_currency"] != payload["currency"]
        assert payload["payout_currency"] == "EUR"
        assert payload["settlement_amount"] != payload["amount"]
        assert payload["settlement_amount"] == "92.50"

    def test_settlement_date_format(self, engine, merchant_server):
        """Settlement date format is YYYY-MM-DD."""
        event = WebhookFactory.create_event(event_type="payment.settled")
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        payload = received[0]["payload"]

        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        assert date_pattern.match(payload["settlement_date"]), (
            f"settlement_date '{payload['settlement_date']}' does not match YYYY-MM-DD"
        )
