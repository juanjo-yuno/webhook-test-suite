import hashlib
import hmac
import json


def generate_signature(payload: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for a webhook payload."""
    message = json.dumps(payload, sort_keys=True, default=str)
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(payload: dict, secret: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature against a webhook payload."""
    expected = generate_signature(payload, secret)
    return hmac.compare_digest(expected, signature)
