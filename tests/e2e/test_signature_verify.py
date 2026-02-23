"""E2E tests for HMAC signature verification."""

import json

import pytest
import requests

from src.merchant_receiver.server import MerchantWebhookServer
from src.utils.crypto import generate_signature
from src.webhook_simulator.signer import WebhookSigner


pytestmark = pytest.mark.e2e


@pytest.fixture
def sig_server(webhook_secret):
    """Merchant server with signature verification enabled."""
    server = MerchantWebhookServer()
    server.enable_signature_verification(webhook_secret)
    server.start()
    yield server
    server.stop()


class TestSignatureVerification:
    """Test HMAC signature verification on the merchant server."""

    def test_valid_signature_accepted(self, engine, webhook_factory, sig_server):
        """Valid signature is accepted with 200 response."""
        # Engine uses the same secret as sig_server (both use webhook_secret)
        event = webhook_factory.create_event("payment.authorized")
        attempts = engine.deliver_with_retry(event, sig_server.url, delay_factor=0)

        assert attempts[-1].status_code == 200
        assert sig_server.get_processed_count() == 1

    def test_invalid_signature_rejected(self, webhook_factory, sig_server):
        """Invalid signature is rejected with 401 response."""
        event = webhook_factory.create_event("payment.authorized")
        payload_str = json.dumps(event.payload, default=str)

        resp = requests.post(
            sig_server.url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": "invalid_signature_value",
                "X-Event-ID": event.event_id,
                "X-Event-Type": event.event_type,
            },
            timeout=5,
        )

        assert resp.status_code == 401
        assert sig_server.get_processed_count() == 0

    def test_missing_signature_rejected(self, webhook_factory, sig_server):
        """Missing signature header is rejected with 401 response."""
        event = webhook_factory.create_event("payment.captured")
        payload_str = json.dumps(event.payload, default=str)

        resp = requests.post(
            sig_server.url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Event-ID": event.event_id,
                "X-Event-Type": event.event_type,
            },
            timeout=5,
        )

        assert resp.status_code == 401
        assert sig_server.get_processed_count() == 0

    def test_tampered_payload_rejected(self, webhook_factory, webhook_secret, sig_server):
        """Payload modified after signing is rejected with 401."""
        event = webhook_factory.create_event("payment.authorized")
        # Sign the original payload
        signature = generate_signature(event.payload, webhook_secret)

        # Tamper with the payload after signing
        tampered_payload = dict(event.payload)
        tampered_payload["amount"] = "999999.99"
        payload_str = json.dumps(tampered_payload, default=str)

        resp = requests.post(
            sig_server.url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Event-ID": event.event_id,
                "X-Event-Type": event.event_type,
            },
            timeout=5,
        )

        assert resp.status_code == 401
        assert sig_server.get_processed_count() == 0

    def test_wrong_secret_rejected(self, webhook_factory, sig_server):
        """Signing with secret A, verifying with secret B -> rejected."""
        event = webhook_factory.create_event("payment.settled")
        wrong_secret = "completely-wrong-secret-key"
        signature = generate_signature(event.payload, wrong_secret)
        payload_str = json.dumps(event.payload, default=str)

        resp = requests.post(
            sig_server.url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Event-ID": event.event_id,
                "X-Event-Type": event.event_type,
            },
            timeout=5,
        )

        assert resp.status_code == 401
        assert sig_server.get_processed_count() == 0
