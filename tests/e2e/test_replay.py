"""E2E tests for WebhookReplayManager with real engine + server."""

import pytest

from src.merchant_receiver.server import MerchantWebhookServer


pytestmark = pytest.mark.e2e


WEBHOOK_SECRET = "test-secret-key-for-hmac"


class TestReplay:
    """Test webhook replay functionality end-to-end."""

    def test_replay_resends_original_payload(
        self, engine, webhook_factory, replay_manager, logger,
    ):
        """Register event, deliver to failing merchant (500), then replay to
        working merchant. Replayed payload matches original fields and has
        _replay: True marker."""
        event = webhook_factory.create_event(
            "payment.authorized", payment_id="pay_replay_original_001",
        )
        replay_manager.register_event(event)

        # Deliver to a server that returns 500
        failing_server = MerchantWebhookServer(secret=WEBHOOK_SECRET)
        failing_server.set_response_code(500)
        failing_server.start()
        try:
            engine.deliver_with_retry(event, failing_server.url, delay_factor=0)
        finally:
            failing_server.stop()

        # Replay to a working server
        working_server = MerchantWebhookServer(secret=WEBHOOK_SECRET)
        working_server.start()
        try:
            attempts = replay_manager.replay_event(event.event_id, working_server.url)

            # Replay delivery succeeded
            assert attempts[-1].status_code == 200

            received = working_server.get_received_events()
            assert len(received) == 1

            replayed_payload = received[0]["payload"]

            # Original fields preserved
            assert replayed_payload["payment_id"] == event.payload["payment_id"]
            assert replayed_payload["amount"] == event.payload["amount"]
            assert replayed_payload["currency"] == event.payload["currency"]
            assert replayed_payload["event_type"] == event.payload["event_type"]
            assert replayed_payload["status"] == event.payload["status"]

            # Replay marker present
            assert replayed_payload["_replay"] is True
        finally:
            working_server.stop()

    def test_replay_marked_in_logs(
        self, engine, webhook_factory, replay_manager, logger, merchant_server,
    ):
        """Replay an event and verify delivery attempts exist in the logger,
        and that the merchant received payload contains _replay: True."""
        event = webhook_factory.create_event("payment.captured")
        replay_manager.register_event(event)

        # Replay to a working merchant
        replay_manager.replay_event(event.event_id, merchant_server.url)

        # Logger should have attempts for this event
        logged = logger.get_attempts(event_id=event.event_id)
        assert len(logged) >= 1
        assert logged[-1].status_code == 200

        # Merchant received the replayed event with _replay flag
        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["payload"]["_replay"] is True

    def test_replay_specific_event_by_id(
        self, engine, webhook_factory, replay_manager, merchant_server,
    ):
        """Register multiple events, replay only one specific event_id.
        Verify only that event was re-delivered to the merchant."""
        event_a = webhook_factory.create_event(
            "payment.authorized", payment_id="pay_specific_a",
        )
        event_b = webhook_factory.create_event(
            "payment.captured", payment_id="pay_specific_b",
        )
        event_c = webhook_factory.create_event(
            "payment.settled", payment_id="pay_specific_c",
        )

        for ev in [event_a, event_b, event_c]:
            replay_manager.register_event(ev)

        # Replay only event_b
        attempts = replay_manager.replay_event(event_b.event_id, merchant_server.url)
        assert attempts[-1].status_code == 200

        received = merchant_server.get_received_events()
        assert len(received) == 1
        assert received[0]["payload"]["payment_id"] == "pay_specific_b"
        assert received[0]["payload"]["event_type"] == "payment.captured"
        assert received[0]["payload"]["_replay"] is True

    def test_replay_failed_deliveries_only(
        self, signer, logger, webhook_factory,
    ):
        """Register 3 events. Deliver A successfully (200), deliver B and C
        to failing server (500). Call replay_failed(url). Only B and C should
        be replayed, not A."""
        from src.webhook_simulator.retry import RetryManager
        from src.webhook_simulator.engine import WebhookDeliveryEngine
        from src.replay.manager import WebhookReplayManager

        # Use a retry manager with 0 retries to keep the test fast and clean
        retry_mgr = RetryManager(max_retries=0)
        eng = WebhookDeliveryEngine(
            signer=signer, retry_manager=retry_mgr, logger=logger, timeout_seconds=5,
        )
        replay_mgr = WebhookReplayManager(engine=eng, logger=logger)

        event_a = webhook_factory.create_event(
            "payment.authorized", payment_id="pay_fail_a",
        )
        event_b = webhook_factory.create_event(
            "payment.captured", payment_id="pay_fail_b",
        )
        event_c = webhook_factory.create_event(
            "payment.settled", payment_id="pay_fail_c",
        )

        for ev in [event_a, event_b, event_c]:
            replay_mgr.register_event(ev)

        # Deliver event_a to a working server (200)
        ok_server = MerchantWebhookServer(secret=WEBHOOK_SECRET)
        ok_server.start()
        try:
            eng.deliver_with_retry(event_a, ok_server.url, delay_factor=0)
        finally:
            ok_server.stop()

        # Deliver events B and C to a failing server (500)
        fail_server = MerchantWebhookServer(secret=WEBHOOK_SECRET)
        fail_server.set_response_code(500)
        fail_server.start()
        try:
            eng.deliver_with_retry(event_b, fail_server.url, delay_factor=0)
            eng.deliver_with_retry(event_c, fail_server.url, delay_factor=0)
        finally:
            fail_server.stop()

        # Replay failed deliveries to a new working server
        replay_server = MerchantWebhookServer(secret=WEBHOOK_SECRET)
        replay_server.start()
        try:
            results = replay_mgr.replay_failed(replay_server.url)

            # Only events B and C were replayed
            assert event_b.event_id in results
            assert event_c.event_id in results
            assert event_a.event_id not in results

            received = replay_server.get_received_events()
            received_payment_ids = {e["payload"]["payment_id"] for e in received}
            assert "pay_fail_b" in received_payment_ids
            assert "pay_fail_c" in received_payment_ids
            assert "pay_fail_a" not in received_payment_ids
        finally:
            replay_server.stop()

    def test_replay_respects_current_merchant_url(
        self, engine, webhook_factory, replay_manager, logger,
    ):
        """Register and deliver an event to URL_1 (fails). Then replay to
        URL_2 (different working server). Verify the replay goes to URL_2,
        not URL_1."""
        event = webhook_factory.create_event(
            "payment.authorized", payment_id="pay_url_switch",
        )
        replay_manager.register_event(event)

        # Deliver to URL_1 (fails with 500)
        server_1 = MerchantWebhookServer(secret=WEBHOOK_SECRET)
        server_1.set_response_code(500)
        server_1.start()
        try:
            engine.deliver_with_retry(event, server_1.url, delay_factor=0)
        finally:
            server_1.stop()

        # Replay to URL_2 (different working server)
        server_2 = MerchantWebhookServer(secret=WEBHOOK_SECRET)
        server_2.start()
        try:
            attempts = replay_manager.replay_event(event.event_id, server_2.url)

            # Replay succeeded at URL_2
            assert attempts[-1].status_code == 200
            assert attempts[-1].url == server_2.url

            # URL_2 received the replayed event
            received_2 = server_2.get_received_events()
            assert len(received_2) == 1
            assert received_2[0]["payload"]["payment_id"] == "pay_url_switch"
            assert received_2[0]["payload"]["_replay"] is True

            # Confirm server_1 never got the replay (only original failed attempts)
            received_1 = server_1.get_received_events()
            for ev in received_1:
                assert "_replay" not in ev["payload"]
        finally:
            server_2.stop()
