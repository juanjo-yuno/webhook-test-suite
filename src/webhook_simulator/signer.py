from src.utils.crypto import generate_signature, verify_signature


class WebhookSigner:
    """Signs and verifies webhook payloads using HMAC-SHA256."""

    def __init__(self, secret: str):
        self.secret = secret

    def sign(self, payload: dict) -> str:
        return generate_signature(payload, self.secret)

    def verify(self, payload: dict, signature: str) -> bool:
        return verify_signature(payload, self.secret, signature)
