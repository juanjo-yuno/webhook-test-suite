# Locust load test for webhook delivery throughput.
#
# How to run:
#   locust -f tests/load/locustfile.py --headless -u 50 -r 10 --run-time 30s --host http://127.0.0.1:8080
#
# The test automatically starts a MerchantWebhookServer on port 8080 via
# on_test_start/on_test_stop events, so no external server is needed.
#
# Throughput target: ~1000 payments/min (50 users * ~20 req/s with short waits).

import json
import logging
import threading

from locust import HttpUser, between, events, task

from src.merchant_receiver.server import MerchantWebhookServer
from src.utils.factories import WebhookFactory
from src.webhook_simulator.signer import WebhookSigner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state: tracking sent vs received for loss assertions
# ---------------------------------------------------------------------------
WEBHOOK_SECRET = "load-test-secret"

_stats_lock = threading.Lock()
_sent_count: int = 0
_success_count: int = 0
_failure_count: int = 0

# Server instance managed by test lifecycle events
_server: MerchantWebhookServer | None = None

# Event types to rotate through
EVENT_TYPES = [
    "payment.authorized",
    "payment.captured",
    "payment.declined",
    "payment.settled",
    "payment.chargeback",
]


def _increment_sent() -> None:
    global _sent_count
    with _stats_lock:
        _sent_count += 1


def _increment_success() -> None:
    global _success_count
    with _stats_lock:
        _success_count += 1


def _increment_failure() -> None:
    global _failure_count
    with _stats_lock:
        _failure_count += 1


# ---------------------------------------------------------------------------
# Locust lifecycle events
# ---------------------------------------------------------------------------
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Start a MerchantWebhookServer on port 8080 before the load test begins."""
    global _server, _sent_count, _success_count, _failure_count

    # Reset counters
    with _stats_lock:
        _sent_count = 0
        _success_count = 0
        _failure_count = 0

    _server = MerchantWebhookServer(
        host="127.0.0.1",
        port=8080,
        secret=WEBHOOK_SECRET,
    )
    _server.start()
    logger.info("MerchantWebhookServer started on port 8080")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Stop the MerchantWebhookServer and report delivery stats."""
    global _server

    received = 0

    if _server is not None:
        received = _server.get_processed_count()
        _server.stop()
        _server = None
        logger.info("MerchantWebhookServer stopped")

    with _stats_lock:
        total_sent = _sent_count
        total_ok = _success_count
        total_fail = _failure_count

    # Report summary
    logger.info(
        "Load test summary: sent=%d, http_ok=%d, http_fail=%d, server_received=%d",
        total_sent,
        total_ok,
        total_fail,
        received,
    )

    if total_sent > 0:
        success_rate = total_ok / total_sent * 100
        loss_rate = (1 - received / total_sent) * 100 if total_sent > 0 else 0

        logger.info("Success rate: %.2f%% (target: >99%%)", success_rate)
        logger.info("Event loss rate: %.2f%% (target: 0%%)", loss_rate)

        if success_rate < 99.0:
            environment.process_exit_code = 1
            logger.error(
                "ASSERTION FAILED: Success rate %.2f%% is below 99%% threshold",
                success_rate,
            )
        if received < total_sent:
            environment.process_exit_code = 1
            logger.error(
                "ASSERTION FAILED: %d events lost (%d sent, %d received)",
                total_sent - received,
                total_sent,
                received,
            )

    # Latency assertion: p95 response time must be below 5000ms (5s)
    for stat in environment.runner.stats.entries.values():
        p95 = stat.get_response_time_percentile(0.95)
        if p95 and p95 > 5000:
            environment.process_exit_code = 1
            logger.error(
                "ASSERTION FAILED: p95 latency %dms exceeds 5000ms for '%s'",
                p95,
                stat.name,
            )


# ---------------------------------------------------------------------------
# Locust user
# ---------------------------------------------------------------------------
class WebhookUser(HttpUser):
    """Simulates a webhook sender delivering payment events to a merchant.

    Uses short wait times to achieve high throughput (~1000 payments/min).
    With 50 concurrent users and wait_time=between(0.01, 0.05), each user
    fires ~20-100 requests/second, easily exceeding the 1000/min target.
    """

    wait_time = between(0.01, 0.05)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._signer = WebhookSigner(WEBHOOK_SECRET)
        self._event_type_index = 0

    def _next_event_type(self) -> str:
        """Rotate through event types round-robin."""
        event_type = EVENT_TYPES[self._event_type_index % len(EVENT_TYPES)]
        self._event_type_index += 1
        return event_type

    @task
    def create_and_deliver_webhook(self) -> None:
        """Create a payment webhook event, sign it, and POST to /webhook."""
        event_type = self._next_event_type()
        event = WebhookFactory.create_event(event_type=event_type)
        signature = self._signer.sign(event.payload)
        body = json.dumps(event.payload, sort_keys=True, default=str)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Event-ID": event.event_id,
            "X-Event-Type": event.event_type,
        }

        _increment_sent()

        with self.client.post(
            "/webhook",
            data=body,
            headers=headers,
            catch_response=True,
            name=f"/webhook [{event_type}]",
        ) as response:
            if response.status_code == 200:
                _increment_success()
                response.success()
            else:
                _increment_failure()
                response.failure(
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
