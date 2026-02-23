"""Integration tests for webhook delivery retry behavior."""

import threading
import time

import pytest

from src.utils.factories import WebhookFactory
from src.webhook_simulator.engine import WebhookDeliveryEngine
from src.webhook_simulator.retry import RetryManager


pytestmark = pytest.mark.integration


class TestDeliveryRetry:
    """Test retry behavior with real HTTP delivery."""

    def test_retry_on_500(self, signer, logger, merchant_server_no_auth):
        """Server returns 500 triggers retries."""
        rm = RetryManager(max_retries=2)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=5
        )
        merchant_server_no_auth.set_response_code(500)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 3  # initial + 2 retries
        assert all(a.status_code == 500 for a in attempts)

    def test_retry_on_502(self, signer, logger, merchant_server_no_auth):
        """Server returns 502 triggers retries."""
        rm = RetryManager(max_retries=2)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=5
        )
        merchant_server_no_auth.set_response_code(502)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 3
        assert all(a.status_code == 502 for a in attempts)

    def test_retry_on_503(self, signer, logger, merchant_server_no_auth):
        """Server returns 503 triggers retries."""
        rm = RetryManager(max_retries=2)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=5
        )
        merchant_server_no_auth.set_response_code(503)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 3
        assert all(a.status_code == 503 for a in attempts)

    def test_retry_on_connection_refused(self, engine, logger):
        """Delivery to a closed port triggers connection_error and retries."""
        event = WebhookFactory.create_event()
        # Use a port that is almost certainly not listening
        url = "http://127.0.0.1:19999/webhook"

        attempts = engine.deliver_with_retry(event, url, delay_factor=0)

        # Should have retried (initial + max_retries = 5 total)
        assert len(attempts) >= 2
        assert all(a.status_code is None for a in attempts)
        assert all(a.error == "connection_error" for a in attempts)

    def test_retry_on_timeout(self, signer, logger, merchant_server_no_auth):
        """Server with delay > engine timeout triggers timeout error and retries."""
        rm = RetryManager(max_retries=2)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=0.5
        )
        merchant_server_no_auth.set_response_delay(3)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        assert len(attempts) == 3
        assert all(a.error == "timeout" for a in attempts)
        assert all(a.status_code is None for a in attempts)

    def test_transient_recovery_500_500_200(self, signer, logger, merchant_server_no_auth):
        """500 -> 500 -> 200: server recovers after two failures.

        Uses a small delay_factor so we have time to reconfigure the server
        between retry attempts.
        """
        rm = RetryManager(max_retries=4)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=5
        )
        # Use a custom schedule with short delays so the test is fast but gives
        # us enough time to reconfigure
        rm.schedule = [0.3, 0.3, 0.3, 0.3]

        server = merchant_server_no_auth
        server.set_response_code(500)
        event = WebhookFactory.create_event()

        results = []

        def deliver():
            results.extend(eng.deliver_with_retry(event, server.url, delay_factor=1.0))

        t = threading.Thread(target=deliver)
        t.start()

        # Wait for at least 2 failed attempts before switching to 200
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if server.get_processed_count() >= 2:
                break
            time.sleep(0.02)

        server.set_response_code(200)
        t.join(timeout=10)

        # First two should be 500, last should be 200
        assert len(results) >= 3
        assert results[0].status_code == 500
        assert results[1].status_code == 500
        assert results[-1].status_code == 200

    def test_max_retries_respected(self, signer, logger, merchant_server_no_auth):
        """Max retries = 4 means 5 total attempts (initial + 4 retries)."""
        rm = RetryManager(max_retries=4)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=5
        )

        merchant_server_no_auth.set_response_code(500)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        # initial attempt + 4 retries = 5 total
        assert len(attempts) == 5
        assert all(a.status_code == 500 for a in attempts)

    def test_all_retry_attempts_logged(self, signer, logger, merchant_server_no_auth):
        """All retry attempts are logged in DeliveryLogger."""
        rm = RetryManager(max_retries=2)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=5
        )

        merchant_server_no_auth.set_response_code(500)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        logged = logger.get_attempts(event_id=event.event_id)
        assert len(logged) == len(attempts)
        assert len(logged) == 3  # initial + 2 retries
