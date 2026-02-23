"""Integration tests for decline webhook payload delivery."""

import pytest

from src.utils.factories import WebhookFactory


pytestmark = pytest.mark.integration


class TestPayloadDecline:
    """Test decline event payload structure and delivery."""

    def test_decline_has_required_fields(self, engine, merchant_server):
        """Decline has decline_code, decline_message, is_soft_decline."""
        event = WebhookFactory.create_event(event_type="payment.declined")
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 1
        payload = received[0]["payload"]

        assert "decline_code" in payload
        assert "decline_message" in payload
        assert "is_soft_decline" in payload

    def test_soft_decline(self, engine, merchant_server):
        """Soft decline: is_soft_decline=True."""
        event = WebhookFactory.create_event(
            event_type="payment.declined",
            is_soft_decline=True,
            decline_code="insufficient_funds",
            decline_message="Insufficient funds",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        payload = received[0]["payload"]

        assert payload["is_soft_decline"] is True

    def test_hard_decline(self, engine, merchant_server):
        """Hard decline: is_soft_decline=False."""
        event = WebhookFactory.create_event(
            event_type="payment.declined",
            is_soft_decline=False,
            decline_code="lost_card",
            decline_message="Lost card",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        payload = received[0]["payload"]

        assert payload["is_soft_decline"] is False

    def test_uncommon_decline_codes(self, engine, merchant_server):
        """Uncommon decline codes: 'do_not_honor' and 'stolen_card'."""
        for code, msg in [("do_not_honor", "Do not honor"), ("stolen_card", "Stolen card")]:
            merchant_server.clear_events()
            event = WebhookFactory.create_event(
                event_type="payment.declined",
                decline_code=code,
                decline_message=msg,
                is_soft_decline=False,
            )
            engine.deliver(event, merchant_server.url)

            received = merchant_server.get_received_events()
            assert len(received) == 1
            payload = received[0]["payload"]

            assert payload["decline_code"] == code
            assert payload["decline_message"] == msg
