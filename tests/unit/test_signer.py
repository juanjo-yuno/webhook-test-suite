import pytest

from src.webhook_simulator.signer import WebhookSigner


class TestSign:
    """Tests for WebhookSigner.sign()."""

    @pytest.mark.unit
    def test_sign_produces_deterministic_output(self, signer):
        payload = {"payment_id": "pay_123", "amount": "100.00"}
        sig1 = signer.sign(payload)
        sig2 = signer.sign(payload)
        assert sig1 == sig2

    @pytest.mark.unit
    def test_sign_output_is_hex_string(self, signer):
        payload = {"payment_id": "pay_123"}
        sig = signer.sign(payload)
        assert isinstance(sig, str)
        # HMAC-SHA256 produces 64 hex chars
        assert len(sig) == 64
        int(sig, 16)  # Raises ValueError if not hex

    @pytest.mark.unit
    def test_different_secrets_produce_different_signatures(self):
        payload = {"payment_id": "pay_123", "amount": "100.00"}
        signer_a = WebhookSigner("secret-a")
        signer_b = WebhookSigner("secret-b")
        assert signer_a.sign(payload) != signer_b.sign(payload)

    @pytest.mark.unit
    def test_empty_payload_produces_valid_signature(self, signer):
        sig = signer.sign({})
        assert isinstance(sig, str)
        assert len(sig) == 64

    @pytest.mark.unit
    def test_unicode_payload_content_works(self, signer):
        payload = {"description": "Pago con tarjeta de credito", "name": "Munchen"}
        sig = signer.sign(payload)
        assert isinstance(sig, str)
        assert len(sig) == 64


class TestVerify:
    """Tests for WebhookSigner.verify()."""

    @pytest.mark.unit
    def test_verify_returns_true_for_valid_signature(self, signer):
        payload = {"payment_id": "pay_123", "amount": "100.00"}
        sig = signer.sign(payload)
        assert signer.verify(payload, sig) is True

    @pytest.mark.unit
    def test_verify_returns_false_for_invalid_signature(self, signer):
        payload = {"payment_id": "pay_123", "amount": "100.00"}
        assert signer.verify(payload, "invalid_signature_value") is False

    @pytest.mark.unit
    def test_verify_returns_false_for_tampered_payload(self, signer):
        payload = {"payment_id": "pay_123", "amount": "100.00"}
        sig = signer.sign(payload)
        tampered = {"payment_id": "pay_123", "amount": "999.99"}
        assert signer.verify(tampered, sig) is False
