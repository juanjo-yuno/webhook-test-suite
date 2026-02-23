"""Integration tests for delivery attempt logging."""

import pytest

from src.utils.factories import WebhookFactory
from src.webhook_simulator.engine import WebhookDeliveryEngine
from src.webhook_simulator.retry import RetryManager


pytestmark = pytest.mark.integration


class TestDeliveryLogging:
    """Test that delivery attempts are properly logged."""

    def test_all_delivery_attempts_logged(self, signer, logger, merchant_server_no_auth):
        """All delivery attempts are logged, including retries."""
        rm = RetryManager(max_retries=2)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=rm, logger=logger, timeout_seconds=5
        )
        merchant_server_no_auth.set_response_code(500)
        event = WebhookFactory.create_event()

        attempts = eng.deliver_with_retry(event, merchant_server_no_auth.url, delay_factor=0)

        logged = logger.get_attempts()
        assert len(logged) == len(attempts)
        assert len(logged) == 3  # initial + 2 retries

    def test_logged_attempt_has_status_code(self, engine, merchant_server_no_auth):
        """Logged attempt has status_code."""
        merchant_server_no_auth.set_response_code(200)
        event = WebhookFactory.create_event()

        engine.deliver(event, merchant_server_no_auth.url)

        logged = engine.logger.get_attempts(event_id=event.event_id)
        assert len(logged) == 1
        assert logged[0].status_code == 200

    def test_logged_attempt_has_response_time(self, engine, merchant_server_no_auth):
        """Logged attempt has response_time_ms > 0."""
        merchant_server_no_auth.set_response_code(200)
        event = WebhookFactory.create_event()

        engine.deliver(event, merchant_server_no_auth.url)

        logged = engine.logger.get_attempts(event_id=event.event_id)
        assert len(logged) == 1
        assert logged[0].response_time_ms > 0

    def test_attempts_queryable_by_event_id(self, engine, merchant_server_no_auth):
        """Attempts are queryable by event_id."""
        merchant_server_no_auth.set_response_code(200)
        event1 = WebhookFactory.create_event()
        event2 = WebhookFactory.create_event()

        engine.deliver(event1, merchant_server_no_auth.url)
        engine.deliver(event2, merchant_server_no_auth.url)

        logged_1 = engine.logger.get_attempts(event_id=event1.event_id)
        logged_2 = engine.logger.get_attempts(event_id=event2.event_id)
        logged_all = engine.logger.get_attempts()

        assert len(logged_1) == 1
        assert len(logged_2) == 1
        assert len(logged_all) == 2
        assert logged_1[0].event_id == event1.event_id
        assert logged_2[0].event_id == event2.event_id
