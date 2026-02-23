"""Integration tests for authorization webhook payload delivery."""

import pytest

from src.utils.factories import WebhookFactory


pytestmark = pytest.mark.integration


class TestPayloadAuthorization:
    """Test authorization event payload structure and delivery."""

    def test_authorization_event_has_all_required_fields(self, engine, merchant_server):
        """Authorization event has payment_id, status, amount, currency, timestamp,
        event_type, and authorization_code."""
        event = WebhookFactory.create_event(
            event_type="payment.authorized",
            authorization_code="AUTH999",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 1
        payload = received[0]["payload"]

        assert "payment_id" in payload
        assert payload["status"] == "AUTHORIZED"
        assert "amount" in payload
        assert "currency" in payload
        assert "timestamp" in payload
        assert payload["event_type"] == "payment.authorized"
        assert payload["authorization_code"] == "AUTH999"

    def test_payload_received_intact(self, engine, merchant_server):
        """Payload is received intact by merchant server."""
        event = WebhookFactory.create_event(
            event_type="payment.authorized",
            amount="250.50",
            currency="EUR",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 1
        payload = received[0]["payload"]

        assert payload["payment_id"] == event.payment_id
        assert payload["amount"] == "250.50"
        assert payload["currency"] == "EUR"
        assert payload["event_type"] == "payment.authorized"

    def test_amount_matches_sent(self, engine, merchant_server):
        """Amount matches what was sent."""
        event = WebhookFactory.create_event(
            event_type="payment.authorized",
            amount="1234.56",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        payload = received[0]["payload"]

        assert payload["amount"] == "1234.56"
