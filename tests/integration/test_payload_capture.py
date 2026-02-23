"""Integration tests for capture webhook payload delivery."""

from datetime import datetime, timezone, timedelta

import pytest

from src.utils.factories import WebhookFactory


pytestmark = pytest.mark.integration


class TestPayloadCapture:
    """Test capture event payload structure and delivery."""

    def test_capture_event_has_captured_amount(self, engine, merchant_server):
        """Capture event has captured_amount field."""
        event = WebhookFactory.create_event(
            event_type="payment.captured",
            captured_amount="100.00",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 1
        payload = received[0]["payload"]

        assert "captured_amount" in payload
        assert payload["captured_amount"] == "100.00"

    def test_partial_capture(self, engine, merchant_server):
        """Partial capture: captured_amount < amount."""
        event = WebhookFactory.create_event(
            event_type="payment.captured",
            amount="500.00",
            captured_amount="200.00",
        )
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        payload = received[0]["payload"]

        assert float(payload["captured_amount"]) < float(payload["amount"])
        assert payload["captured_amount"] == "200.00"
        assert payload["amount"] == "500.00"

    def test_timestamp_ordering_capture_after_auth(self, engine, merchant_server):
        """Capture timestamp > auth timestamp."""
        auth_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        capture_time = auth_time + timedelta(hours=1)

        # Build events with explicit payload timestamps
        # We must set the timestamp inside the payload, not as a top-level override
        # since the factory uses 'timestamp' as both a positional arg and event field.
        auth_event = WebhookFactory.create_event(
            event_type="payment.authorized",
            payload={"timestamp": auth_time.isoformat()},
        )
        capture_event = WebhookFactory.create_event(
            event_type="payment.captured",
            payment_id=auth_event.payment_id,
            payload={"timestamp": capture_time.isoformat()},
        )

        engine.deliver(auth_event, merchant_server.url)
        engine.deliver(capture_event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 2

        auth_ts = received[0]["payload"]["timestamp"]
        capture_ts = received[1]["payload"]["timestamp"]

        assert capture_ts > auth_ts
