"""E2E tests for invalid/missing fields and malformed payloads."""

import json

import pytest
import requests

from src.utils.crypto import generate_signature


pytestmark = pytest.mark.e2e


class TestMalformedPayload:
    """Test invalid/missing fields in webhook payloads."""

    def test_missing_payment_id_returns_400(self, merchant_server, webhook_secret):
        """Missing payment_id field returns 400 response."""
        payload = {
            "event_type": "payment.authorized",
            "amount": "100.00",
            "currency": "USD",
            "timestamp": "2026-01-15T12:00:00+00:00",
            "status": "AUTHORIZED",
        }
        signature = generate_signature(payload, webhook_secret)

        resp = requests.post(
            merchant_server.url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Event-ID": "evt_test_missing_pid",
                "X-Event-Type": "payment.authorized",
            },
            timeout=5,
        )

        assert resp.status_code == 400
        assert "payment_id" in resp.json()["error"]

    def test_missing_event_type_returns_400(self, merchant_server, webhook_secret):
        """Missing event_type field returns 400 response."""
        payload = {
            "payment_id": "pay_test_001",
            "amount": "100.00",
            "currency": "USD",
            "timestamp": "2026-01-15T12:00:00+00:00",
            "status": "AUTHORIZED",
        }
        signature = generate_signature(payload, webhook_secret)

        resp = requests.post(
            merchant_server.url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Event-ID": "evt_test_missing_type",
                "X-Event-Type": "payment.authorized",
            },
            timeout=5,
        )

        assert resp.status_code == 400
        assert "event_type" in resp.json()["error"]

    def test_invalid_amount_returns_400(self, merchant_server, webhook_secret):
        """Non-numeric amount (like 'abc') returns 400 response."""
        payload = {
            "payment_id": "pay_test_002",
            "event_type": "payment.authorized",
            "amount": "abc",
            "currency": "USD",
            "timestamp": "2026-01-15T12:00:00+00:00",
            "status": "AUTHORIZED",
        }
        signature = generate_signature(payload, webhook_secret)

        resp = requests.post(
            merchant_server.url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Event-ID": "evt_test_bad_amount",
                "X-Event-Type": "payment.authorized",
            },
            timeout=5,
        )

        assert resp.status_code == 400
        assert "amount" in resp.json()["error"]

    def test_empty_json_body_returns_400(self, merchant_server, webhook_secret):
        """Empty JSON body ({}) returns 400 response."""
        payload = {}
        signature = generate_signature(payload, webhook_secret)

        resp = requests.post(
            merchant_server.url,
            data=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Event-ID": "evt_test_empty_json",
                "X-Event-Type": "payment.authorized",
            },
            timeout=5,
        )

        assert resp.status_code == 400

    def test_completely_malformed_json_returns_400(self, merchant_server):
        """Completely malformed JSON (not JSON at all) returns 400 response."""
        resp = requests.post(
            merchant_server.url,
            data="this is not json {{{",
            headers={
                "Content-Type": "application/json",
                "X-Event-ID": "evt_test_bad_json",
                "X-Event-Type": "payment.authorized",
            },
            timeout=5,
        )

        assert resp.status_code == 400
        assert "invalid JSON" in resp.json()["error"]
