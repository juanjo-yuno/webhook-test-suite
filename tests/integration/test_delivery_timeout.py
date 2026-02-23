"""Integration tests for webhook delivery timeout handling."""

import pytest

from src.utils.factories import WebhookFactory
from src.webhook_simulator.engine import WebhookDeliveryEngine
from src.webhook_simulator.retry import RetryManager


pytestmark = pytest.mark.integration


class TestDeliveryTimeout:
    """Test timeout behavior during webhook delivery."""

    def test_slow_endpoint_results_in_timeout_error(
        self, signer, retry_manager, logger, merchant_server_no_auth
    ):
        """Slow endpoint (delay > timeout) results in error='timeout'."""
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=retry_manager, logger=logger, timeout_seconds=0.5
        )
        merchant_server_no_auth.set_response_delay(3)
        event = WebhookFactory.create_event()

        attempt = eng.deliver(event, merchant_server_no_auth.url)

        assert attempt.error == "timeout"
        assert attempt.status_code is None

    def test_configurable_timeout(self, signer, logger, merchant_server_no_auth):
        """Engine with timeout_seconds=1 times out when server delay=3."""
        rm = RetryManager(max_retries=0)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=1
        )
        merchant_server_no_auth.set_response_delay(3)
        event = WebhookFactory.create_event()

        attempt = eng.deliver(event, merchant_server_no_auth.url)

        assert attempt.error == "timeout"
        assert attempt.status_code is None

    def test_timeout_logged_with_status_code_none(
        self, signer, logger, merchant_server_no_auth
    ):
        """Timeout is logged as a delivery attempt with status_code=None."""
        rm = RetryManager(max_retries=0)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=0.5
        )
        merchant_server_no_auth.set_response_delay(3)
        event = WebhookFactory.create_event()

        eng.deliver(event, merchant_server_no_auth.url)

        logged = logger.get_attempts(event_id=event.event_id)
        assert len(logged) == 1
        assert logged[0].status_code is None
        assert logged[0].error == "timeout"

    def test_timeout_triggers_retry(self, signer, logger, merchant_server_no_auth):
        """Timeout triggers retry via deliver_with_retry."""
        rm = RetryManager(max_retries=2)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=0.5
        )
        merchant_server_no_auth.set_response_delay(3)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        # initial + 2 retries = 3 total, all timed out
        assert len(attempts) == 3
        assert all(a.error == "timeout" for a in attempts)
        assert all(a.status_code is None for a in attempts)
