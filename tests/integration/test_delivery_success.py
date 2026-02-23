"""Integration tests for happy-path webhook delivery."""

import pytest

from src.utils.factories import WebhookFactory


pytestmark = pytest.mark.integration


class TestDeliverySuccess:
    """Test successful delivery to endpoints returning 2xx."""

    def test_delivery_to_200_endpoint(self, engine, merchant_server):
        """Delivery to a 200 endpoint succeeds with status_code=200."""
        merchant_server.set_response_code(200)
        event = WebhookFactory.create_event()
        attempt = engine.deliver(event, merchant_server.url)

        assert attempt.status_code == 200
        assert attempt.error is None

    def test_delivery_to_201_endpoint(self, engine, merchant_server):
        """Delivery to a 201 endpoint succeeds."""
        merchant_server.set_response_code(201)
        event = WebhookFactory.create_event()
        attempt = engine.deliver(event, merchant_server.url)

        assert attempt.status_code == 201
        assert attempt.error is None

    def test_delivery_to_204_endpoint(self, engine, merchant_server):
        """Delivery to a 204 endpoint succeeds."""
        merchant_server.set_response_code(204)
        event = WebhookFactory.create_event()
        attempt = engine.deliver(event, merchant_server.url)

        assert attempt.status_code == 204
        assert attempt.error is None

    def test_delivery_uses_post_with_correct_content_type(self, engine, merchant_server):
        """Delivery uses POST method with correct Content-Type header."""
        event = WebhookFactory.create_event()
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["headers"]["Content-Type"] == "application/json"

    def test_delivery_includes_custom_headers(self, engine, merchant_server):
        """Delivery includes X-Webhook-Signature, X-Event-ID, X-Event-Type headers."""
        event = WebhookFactory.create_event(event_type="payment.authorized")
        engine.deliver(event, merchant_server.url)

        received = merchant_server.get_received_events()
        assert len(received) == 1
        headers = received[0]["headers"]

        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"] != ""
        assert headers["X-Event-ID"] == event.event_id
        assert headers["X-Event-Type"] == "payment.authorized"
