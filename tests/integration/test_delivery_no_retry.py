"""Integration tests for no-retry on 4xx client errors."""

import pytest

from src.utils.factories import WebhookFactory


pytestmark = pytest.mark.integration


class TestDeliveryNoRetry:
    """Test that 4xx client errors are NOT retried."""

    def test_no_retry_on_400(self, engine, merchant_server_no_auth):
        """No retry on 400 Bad Request."""
        merchant_server_no_auth.set_response_code(400)
        event = WebhookFactory.create_event()

        attempts = engine.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 400

    def test_no_retry_on_401(self, engine, merchant_server_no_auth):
        """No retry on 401 Unauthorized."""
        merchant_server_no_auth.set_response_code(401)
        event = WebhookFactory.create_event()

        attempts = engine.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 401

    def test_no_retry_on_404(self, engine, merchant_server_no_auth):
        """No retry on 404 Not Found."""
        merchant_server_no_auth.set_response_code(404)
        event = WebhookFactory.create_event()

        attempts = engine.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 404

    def test_no_retry_on_422(self, engine, merchant_server_no_auth):
        """No retry on 422 Unprocessable Entity."""
        merchant_server_no_auth.set_response_code(422)
        event = WebhookFactory.create_event()

        attempts = engine.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 1
        assert attempts[0].status_code == 422
