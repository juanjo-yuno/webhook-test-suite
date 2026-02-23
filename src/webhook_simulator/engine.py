import json
import time
import uuid
from datetime import datetime, timezone

import requests

from src.models.delivery import DeliveryAttempt
from src.models.webhook import WebhookEvent
from src.webhook_simulator.logger import DeliveryLogger
from src.webhook_simulator.retry import RetryManager
from src.webhook_simulator.signer import WebhookSigner


class WebhookDeliveryEngine:
    """Delivers webhook events to merchant endpoints with retry support."""

    def __init__(
        self,
        signer: WebhookSigner,
        retry_manager: RetryManager,
        logger: DeliveryLogger,
        timeout_seconds: float = 30,
    ):
        self.signer = signer
        self.retry_manager = retry_manager
        self.logger = logger
        self.timeout_seconds = timeout_seconds

    def deliver(self, event: WebhookEvent, url: str) -> DeliveryAttempt:
        """Deliver a single webhook event. Returns the delivery attempt result."""
        payload = event.payload
        signature = self.signer.sign(payload)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Event-ID": event.event_id,
            "X-Event-Type": event.event_type,
        }

        start = time.monotonic()
        status_code = None
        error = None

        try:
            resp = requests.post(
                url,
                data=json.dumps(payload, default=str),
                headers=headers,
                timeout=self.timeout_seconds,
            )
            status_code = resp.status_code
        except requests.exceptions.Timeout:
            error = "timeout"
        except requests.exceptions.ConnectionError:
            error = "connection_error"
        except requests.exceptions.RequestException as e:
            error = str(e)

        elapsed_ms = (time.monotonic() - start) * 1000

        attempt = DeliveryAttempt(
            attempt_id=f"att_{uuid.uuid4().hex[:16]}",
            event_id=event.event_id,
            url=url,
            status_code=status_code,
            timestamp=datetime.now(timezone.utc),
            response_time_ms=elapsed_ms,
            error=error,
        )
        self.logger.log(attempt)
        return attempt

    def deliver_with_retry(
        self,
        event: WebhookEvent,
        url: str,
        delay_factor: float = 1.0,
    ) -> list[DeliveryAttempt]:
        """Deliver with automatic retries on failure.

        Args:
            event: The webhook event to deliver.
            url: The merchant endpoint URL.
            delay_factor: Multiplier for retry delays (use 0 in tests to skip waits).

        Returns:
            List of all delivery attempts made.
        """
        attempts = []
        retry_count = 0

        while True:
            attempt = self.deliver(event, url)
            attempts.append(attempt)

            # Success
            if attempt.status_code is not None and 200 <= attempt.status_code < 300:
                break

            # Check if we should retry
            if not self.retry_manager.should_retry(attempt.status_code):
                break

            if not self.retry_manager.has_attempts_remaining(retry_count):
                break

            delay = self.retry_manager.next_delay(retry_count) * delay_factor
            if delay > 0:
                time.sleep(delay)

            retry_count += 1

        return attempts
