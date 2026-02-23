"""E2E tests for out-of-order webhook delivery."""

from datetime import datetime, timezone, timedelta

import pytest


pytestmark = pytest.mark.e2e


class TestOutOfOrderDelivery:
    """Test out-of-order webhook delivery scenarios."""

    def test_capture_before_auth_both_received(
        self, engine, webhook_factory, merchant_server,
    ):
        """Capture delivered before auth - both still received by merchant."""
        payment_id = "pay_ooo_cap_auth_001"

        auth_event = webhook_factory.create_event(
            "payment.authorized", payment_id=payment_id,
        )
        cap_event = webhook_factory.create_event(
            "payment.captured", payment_id=payment_id,
        )

        # Deliver capture first, then auth
        cap_attempts = engine.deliver_with_retry(cap_event, merchant_server.url, delay_factor=0)
        auth_attempts = engine.deliver_with_retry(auth_event, merchant_server.url, delay_factor=0)

        assert cap_attempts[-1].status_code == 200
        assert auth_attempts[-1].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 2
        assert received[0]["payload"]["event_type"] == "payment.captured"
        assert received[1]["payload"]["event_type"] == "payment.authorized"

    def test_settle_before_capture_both_received(
        self, engine, webhook_factory, merchant_server,
    ):
        """Settle delivered before capture - both still received."""
        payment_id = "pay_ooo_settle_cap_001"

        cap_event = webhook_factory.create_event(
            "payment.captured", payment_id=payment_id,
        )
        settle_event = webhook_factory.create_event(
            "payment.settled", payment_id=payment_id,
        )

        # Deliver settle first, then capture
        settle_attempts = engine.deliver_with_retry(
            settle_event, merchant_server.url, delay_factor=0,
        )
        cap_attempts = engine.deliver_with_retry(
            cap_event, merchant_server.url, delay_factor=0,
        )

        assert settle_attempts[-1].status_code == 200
        assert cap_attempts[-1].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 2
        assert received[0]["payload"]["event_type"] == "payment.settled"
        assert received[1]["payload"]["event_type"] == "payment.captured"

    def test_events_can_be_reordered_by_timestamp(
        self, engine, webhook_factory, merchant_server,
    ):
        """Events received out of order can be reordered by timestamp field."""
        payment_id = "pay_ooo_reorder_001"
        base_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        auth_event = webhook_factory.create_event(
            "payment.authorized", payment_id=payment_id,
        )
        auth_event.payload["timestamp"] = base_time.isoformat()

        cap_event = webhook_factory.create_event(
            "payment.captured", payment_id=payment_id,
        )
        cap_event.payload["timestamp"] = (base_time + timedelta(minutes=5)).isoformat()

        settle_event = webhook_factory.create_event(
            "payment.settled", payment_id=payment_id,
        )
        settle_event.payload["timestamp"] = (base_time + timedelta(minutes=10)).isoformat()

        # Deliver out of order: settle, auth, capture
        engine.deliver_with_retry(settle_event, merchant_server.url, delay_factor=0)
        engine.deliver_with_retry(auth_event, merchant_server.url, delay_factor=0)
        engine.deliver_with_retry(cap_event, merchant_server.url, delay_factor=0)

        received = merchant_server.get_received_events()
        assert len(received) == 3

        # Received out of order
        received_types = [e["payload"]["event_type"] for e in received]
        assert received_types == ["payment.settled", "payment.authorized", "payment.captured"]

        # But can be sorted by timestamp
        sorted_events = sorted(received, key=lambda e: e["payload"]["timestamp"])
        sorted_types = [e["payload"]["event_type"] for e in sorted_events]
        assert sorted_types == ["payment.authorized", "payment.captured", "payment.settled"]

    def test_all_events_delivered_even_if_out_of_order(
        self, engine, webhook_factory, merchant_server,
    ):
        """All events are delivered even if sent out of logical order."""
        payment_id = "pay_ooo_all_delivered_001"

        events = [
            webhook_factory.create_event("payment.chargeback", payment_id=payment_id),
            webhook_factory.create_event("payment.settled", payment_id=payment_id),
            webhook_factory.create_event("payment.authorized", payment_id=payment_id),
            webhook_factory.create_event("payment.captured", payment_id=payment_id),
        ]

        for event in events:
            attempts = engine.deliver_with_retry(event, merchant_server.url, delay_factor=0)
            assert attempts[-1].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 4

        received_types = {e["payload"]["event_type"] for e in received}
        assert received_types == {
            "payment.chargeback",
            "payment.settled",
            "payment.authorized",
            "payment.captured",
        }
