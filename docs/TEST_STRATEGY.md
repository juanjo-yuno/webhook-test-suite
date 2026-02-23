# Test Strategy

## 1. Test Pyramid Strategy

This suite follows a classic test pyramid to balance feedback speed with confidence.

**Unit tests (~55 tests)** form the pyramid base. They validate individual components in
isolation: `RetryManager` backoff schedule, `WebhookSigner` HMAC generation, `MetricsCollector`
rolling-window arithmetic, `PaymentFactory` defaults, and `AlertManager` fire-once semantics.
Unit tests run without network I/O or threading, completing in under two seconds.

**Integration tests (~38 tests)** occupy the middle layer. They verify component interactions:
the delivery engine posting signed payloads to a threaded HTTP server, the merchant receiver
validating signatures and enforcing idempotency, and the replay manager coordinating with the
logger to re-deliver failed events. Each test spins up a `MerchantWebhookServer` on an
ephemeral port, exercises the engine over HTTP, and tears it down. This layer catches wiring
bugs such as incorrect header propagation and signature verification failures across the
network boundary.

**End-to-end tests (~36 tests)** sit at the pyramid top. They exercise complete business
scenarios: full payment lifecycle, out-of-order webhook handling, the 4-hour blackout
simulation, multi-currency settlement with FX conversion, and partial-capture flows.
E2E tests use `delay_factor=0` to eliminate real wait times while preserving the full
retry and alerting code path.

This distribution (43% unit, 29% integration, 28% E2E) keeps the base wide for speed
while maintaining enough higher-layer coverage for integration and business-logic defects.

## 2. Framework Rationale

The suite is built on **Python 3.12+**, **pytest**, and **requests**.

**pytest** was chosen over `unittest` for its fixture system, which provides dependency
injection and automatic setup/teardown. Each test receives fresh instances through fixtures
in `conftest.py`, eliminating shared mutable state. Markers (`@pytest.mark.unit`,
`integration`, `e2e`, `load`) enable selective execution. The `pytest-xdist` plugin
supports parallel execution, and `pytest-cov` produces coverage reports.

**requests** is used for real HTTP calls rather than mocking the transport layer. The
engine posts actual requests to a `MerchantWebhookServer` on localhost, catching real
serialization, header, and timeout behavior that mocked HTTP clients would miss.

**Locust** handles load testing with a Python-native framework that reuses the same
`requests`-based patterns, avoiding separate tools like k6 or JMeter. Selenium was
excluded because the system under test has no UI surface.

## 3. Edge Cases

The suite explicitly covers these edge cases:

- **Out-of-order webhooks**: `payment.captured` arriving before `payment.authorized`.
- **Duplicate/idempotent delivery**: the same `event_id` delivered twice; the server must accept both but process only once.
- **Malformed payloads**: missing required fields, invalid JSON, non-numeric amounts.
- **Partial captures**: `captured_amount` less than the authorized amount.
- **Multi-currency**: payments in USD, EUR, BRL, MXN; settlement in a different payout currency (FX scenarios).
- **Uncommon decline codes**: soft declines (`is_soft_decline=True`) vs hard declines, chargeback events with specific decline codes.
- **FX settlement**: `settlement_amount` and `payout_currency` differing from the original payment currency.
- **Signature tampering**: payloads delivered with an incorrect HMAC signature, or missing the signature header entirely.
- **Connection timeouts**: merchant server configured with `set_response_delay()` exceeding the engine timeout.
- **4-hour blackout simulation**: the NovaPay scenario where the merchant endpoint returns 503 for all retry attempts, exhausting the full retry schedule (30s, 5m, 30m, 2h), then replay recovers the events once the endpoint is restored.

## 4. Test Data and Isolation

Test data is generated through the factory pattern. `PaymentFactory.create()` produces
`Payment` instances with unique IDs, sensible defaults (100.00 USD, AUTHORIZED), and
keyword overrides. `WebhookFactory.create_event()` builds `WebhookEvent` objects with
payloads that vary by event type (authorization codes, decline codes, settlement amounts).

Factories use `uuid4` for identifiers, guaranteeing uniqueness without coordination.
Every test that needs a server gets its own `MerchantWebhookServer` via a pytest fixture,
bound to port 0 (OS-assigned ephemeral port) so tests run in parallel without port
conflicts. The fixture teardown calls `server.stop()`, ensuring cleanup even on failure.

No shared state exists between tests. Each gets fresh `engine`, `logger`, `metrics`, and
`alert_manager` instances. `MetricsCollector` uses `time.monotonic()` for its rolling
window, making it immune to wall-clock changes.

## 5. Trade-offs

**Full mock vs real APIs.** The suite uses a fully mocked merchant server rather than
calling real provider APIs. This gives deterministic results, sub-second execution, and
CI-friendliness. The trade-off is that real provider quirks (rate limiting, certificate
changes) are not covered. Acceptable because the system under test is the delivery
engine, not the provider integration.

**Threading HTTP server vs subprocess.** The `MerchantWebhookServer` runs in a daemon
thread using `http.server.HTTPServer`. A subprocess approach would provide stronger
isolation but adds startup latency and port coordination complexity. Threading was
chosen for simplicity: startup is instant, and the daemon flag ensures cleanup.

**Real delays vs `delay_factor=0`.** The retry schedule includes delays up to 2 hours.
Tests use `delay_factor=0` to skip waits while exercising the full retry logic path.
The parameter is configurable for timing-sensitive environments.

**Multi-region testing.** Not simulated. Deferred as out of scope for the initial version.

## 6. Ambiguity Resolution

Several requirements were ambiguous during design. Here is how each was resolved:

- **Payload format**: rather than modeling provider-specific payload schemas (Stripe, Adyen, etc.), a generic format was adopted with six required fields (`payment_id`, `event_type`, `amount`, `currency`, `timestamp`, `status`) and optional event-specific fields. This keeps the test suite provider-agnostic.
- **Retry schedule**: instead of hardcoding retry intervals, the `RetryManager` accepts a configurable `schedule` list. The default `[30, 300, 1800, 7200]` matches NovaPay's production schedule, but tests can override it for faster execution or different scenarios.
- **Signature method**: HMAC-SHA256 was chosen as the standard signature algorithm. The `WebhookSigner` uses `json.dumps(payload, sort_keys=True)` for canonical serialization, avoiding ambiguity in payload ordering.
- **Alerting behavior**: the `AlertManager` uses fire-once semantics. When the failure rate crosses the threshold, one alert is emitted. Subsequent checks while the rate remains elevated do not fire additional alerts, preventing alert storms. The alert resets only when the rate drops back below the threshold.
