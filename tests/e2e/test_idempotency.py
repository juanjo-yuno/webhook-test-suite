"""E2E tests for duplicate webhook / idempotency handling."""

import pytest

from src.merchant_receiver.server import MerchantWebhookServer


pytestmark = pytest.mark.e2e


@pytest.fixture
def idempotent_server(webhook_secret):
    """Merchant server with idempotency enabled."""
    server = MerchantWebhookServer(secret=webhook_secret)
    server.enable_idempotency()
    server.start()
    yield server
    server.stop()


class TestIdempotency:
    """Test duplicate webhook handling with idempotency enabled."""

    def test_duplicate_webhook_processed_once(self, engine, webhook_factory, idempotent_server):
        """Duplicate webhook (same event_id) processed only once."""
        event = webhook_factory.create_event("payment.authorized")

        # Deliver the same event twice
        engine.deliver_with_retry(event, idempotent_server.url, delay_factor=0)
        engine.deliver_with_retry(event, idempotent_server.url, delay_factor=0)

        assert idempotent_server.get_processed_count() == 1
        assert idempotent_server.was_event_processed(event.event_id)

    def test_duplicate_returns_200(self, engine, webhook_factory, idempotent_server):
        """Duplicate delivery returns 200, not an error."""
        event = webhook_factory.create_event("payment.captured")

        first = engine.deliver_with_retry(event, idempotent_server.url, delay_factor=0)
        second = engine.deliver_with_retry(event, idempotent_server.url, delay_factor=0)

        assert first[-1].status_code == 200
        assert second[-1].status_code == 200

    def test_triple_delivery_single_processing(self, engine, webhook_factory, idempotent_server):
        """Triple delivery still results in single processing."""
        event = webhook_factory.create_event("payment.settled")

        for _ in range(3):
            attempts = engine.deliver_with_retry(event, idempotent_server.url, delay_factor=0)
            assert attempts[-1].status_code == 200

        assert idempotent_server.get_processed_count() == 1

    def test_different_events_same_payment_both_processed(
        self, engine, webhook_factory, idempotent_server,
    ):
        """Different events for same payment_id are both processed."""
        payment_id = "pay_shared_payment_001"

        auth_event = webhook_factory.create_event(
            "payment.authorized", payment_id=payment_id,
        )
        cap_event = webhook_factory.create_event(
            "payment.captured", payment_id=payment_id,
        )

        engine.deliver_with_retry(auth_event, idempotent_server.url, delay_factor=0)
        engine.deliver_with_retry(cap_event, idempotent_server.url, delay_factor=0)

        assert idempotent_server.get_processed_count() == 2
        assert idempotent_server.was_event_processed(auth_event.event_id)
        assert idempotent_server.was_event_processed(cap_event.event_id)

    def test_idempotency_key_is_event_id_header(self, engine, webhook_factory, idempotent_server):
        """Idempotency key is the event_id from X-Event-ID header."""
        event = webhook_factory.create_event("payment.authorized")

        engine.deliver_with_retry(event, idempotent_server.url, delay_factor=0)

        received = idempotent_server.get_received_events()
        assert len(received) == 1
        assert received[0]["headers"]["X-Event-ID"] == event.event_id

        # Deliver again with same event_id - should not add to received
        engine.deliver_with_retry(event, idempotent_server.url, delay_factor=0)
        assert idempotent_server.get_processed_count() == 1
