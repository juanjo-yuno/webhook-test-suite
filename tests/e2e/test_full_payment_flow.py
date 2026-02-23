"""E2E tests for full payment lifecycle webhook delivery."""

import pytest


pytestmark = pytest.mark.e2e


class TestFullPaymentFlow:
    """Full payment lifecycle tests using real engine + merchant server."""

    def test_authorization_webhook_delivered(self, engine, webhook_factory, merchant_server):
        """Authorization webhook is delivered and processed by merchant."""
        event = webhook_factory.create_event("payment.authorized")
        attempts = engine.deliver_with_retry(event, merchant_server.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["payload"]["event_type"] == "payment.authorized"
        assert received[0]["payload"]["status"] == "AUTHORIZED"
        assert "authorization_code" in received[0]["payload"]

    def test_capture_webhook_delivered(self, engine, webhook_factory, merchant_server):
        """Capture webhook is delivered and processed by merchant."""
        event = webhook_factory.create_event("payment.captured")
        attempts = engine.deliver_with_retry(event, merchant_server.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["payload"]["event_type"] == "payment.captured"
        assert received[0]["payload"]["status"] == "CAPTURED"
        assert "captured_amount" in received[0]["payload"]

    def test_decline_webhook_delivered(self, engine, webhook_factory, merchant_server):
        """Decline webhook is delivered and processed by merchant."""
        event = webhook_factory.create_event("payment.declined")
        attempts = engine.deliver_with_retry(event, merchant_server.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["payload"]["event_type"] == "payment.declined"
        assert received[0]["payload"]["status"] == "DECLINED"
        assert received[0]["payload"]["decline_code"] == "insufficient_funds"

    def test_settlement_webhook_delivered(self, engine, webhook_factory, merchant_server):
        """Settlement webhook is delivered and processed by merchant."""
        event = webhook_factory.create_event("payment.settled")
        attempts = engine.deliver_with_retry(event, merchant_server.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["payload"]["event_type"] == "payment.settled"
        assert received[0]["payload"]["status"] == "SETTLED"
        assert "settlement_date" in received[0]["payload"]
        assert "settlement_amount" in received[0]["payload"]

    def test_chargeback_webhook_delivered(self, engine, webhook_factory, merchant_server):
        """Chargeback webhook is delivered and processed by merchant."""
        event = webhook_factory.create_event("payment.chargeback")
        attempts = engine.deliver_with_retry(event, merchant_server.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["payload"]["event_type"] == "payment.chargeback"
        assert received[0]["payload"]["status"] == "CHARGEBACK"
        assert received[0]["payload"]["decline_code"] == "chargeback"

    def test_full_lifecycle_auth_capture_settle(self, engine, webhook_factory, merchant_server):
        """Full lifecycle: auth -> capture -> settle all delivered in order."""
        payment_id = "pay_lifecycle_test_001"

        auth_event = webhook_factory.create_event(
            "payment.authorized", payment_id=payment_id,
        )
        cap_event = webhook_factory.create_event(
            "payment.captured", payment_id=payment_id,
        )
        settle_event = webhook_factory.create_event(
            "payment.settled", payment_id=payment_id,
        )

        for event in [auth_event, cap_event, settle_event]:
            attempts = engine.deliver_with_retry(event, merchant_server.url, delay_factor=0)
            assert attempts[-1].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 3

        types = [e["payload"]["event_type"] for e in received]
        assert types == ["payment.authorized", "payment.captured", "payment.settled"]

        # All share the same payment_id
        for e in received:
            assert e["payload"]["payment_id"] == payment_id
