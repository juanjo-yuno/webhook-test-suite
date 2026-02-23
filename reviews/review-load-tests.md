# Review: Load Tests

## Summary
FAIL -- Two critical issues prevent reliable CI usage: assertions do not affect the process exit code, and the latency threshold check is missing entirely. Additionally, the server uses single-threaded `HTTPServer` which will serialize all requests under load, skewing results.

## Checklist
| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Locust user class properly defined with @task decorators | PASS | `WebhookUser(HttpUser)` with `@task` on `create_and_deliver_webhook`. Correct inheritance and decorator usage. |
| 2 | Target: 1000 payments/min throughput | PASS | `wait_time=between(0.01, 0.05)` with 50 users far exceeds 16.7 req/s (1000/min). Example command uses `--headless -u 50 -r 10 --run-time 30s`. |
| 3 | Assertions: no events lost, latency < 5s, success rate > 99% | FAIL | Success rate check (>99%) and event loss check exist but only as log messages. **Latency < 5s assertion is completely missing.** No p95/p99 latency validation anywhere. |
| 4 | Can run in headless mode (CI-compatible) | PASS | Example command includes `--headless`. No interactive prompts. No user input required. |
| 5 | Uses webhook simulator and merchant receiver from src/ | PASS | Imports and uses `MerchantWebhookServer`, `WebhookFactory`, and `WebhookSigner` from src/. |
| 6 | Results are machine-parseable (for CI pass/fail) | FAIL | Assertions are logged via `logger.error`/`logger.warning` but do **not** set a non-zero exit code. Locust will always exit 0 regardless of assertion outcomes. CI cannot determine pass/fail from exit code alone. |
| 7 | Proper server lifecycle (on_test_start / on_test_stop) | PARTIAL | Server starts in `on_test_start` and stops in `on_test_stop`. Counters are reset. However, there is a bug: if `_server is None` at stop time, `received` is used uninitialized on line 98+, causing an `UnboundLocalError`. |
| 8 | Varies event types (not just one type) | PASS | Rotates round-robin through 4 types: `payment.authorized`, `payment.captured`, `payment.declined`, `payment.settled`. Minor: `payment.chargeback` is supported by the factory but not included. |

## Issues Found

### Critical

**C1: Assertions do not set process exit code (lines 118-129)**

The `on_test_stop` handler logs errors when success rate < 99% or events are lost, but never sets `environment.process_exit_code`. Locust will exit 0 even when all assertions fail, making CI pipelines unable to detect failures.

Fix: Use `environment.process_exit_code = 1` when any assertion fails:
```python
if success_rate < 99.0:
    environment.process_exit_code = 1
    logger.error(...)
if received < total_sent:
    environment.process_exit_code = 1
    logger.error(...)
```

**C2: Missing latency assertion (requirement: latency < 5s)**

There is no check on response time percentiles (p95, p99, or even average). The requirement explicitly calls for `latency < 5s`. Locust exposes `environment.runner.stats` which includes percentile data.

Fix: Add latency check in `on_test_stop`:
```python
for stat in environment.runner.stats.entries.values():
    p95 = stat.get_response_time_percentile(0.95)
    if p95 and p95 > 5000:  # 5000ms = 5s
        environment.process_exit_code = 1
        logger.error("ASSERTION FAILED: p95 latency %dms exceeds 5000ms", p95)
```

### Moderate

**M1: `received` variable may be unbound (line 97-113)**

If `_server` is `None` when `on_test_stop` fires, the `received` variable is never assigned but is referenced on lines 104 and 113. This will raise `UnboundLocalError`.

Fix: Initialize `received = 0` before the `if _server is not None:` block.

**M2: `HTTPServer` is single-threaded (src/merchant_receiver/server.py, line 138)**

The server uses `http.server.HTTPServer` which handles one request at a time. With 50 concurrent Locust users sending rapid-fire requests, all requests serialize through a single thread. This will artificially inflate response times and may cause Locust timeouts under load, producing misleading results.

Fix: Use `http.server.ThreadingHTTPServer` (available in Python 3.7+) or apply `socketserver.ThreadingMixIn`:
```python
from http.server import ThreadingHTTPServer
# Replace HTTPServer with ThreadingHTTPServer in start()
```
Note: This is a change to src/ which may affect other tests. Evaluate impact before changing.

### Minor

**m1: `payment.chargeback` not included in EVENT_TYPES (line 37-42)**

The `WebhookFactory._build_payload` supports `payment.chargeback` but the load test only rotates through 4 of the 5 supported event types. Adding it would improve coverage.

**m2: Event loss check uses `logger.warning` instead of `logger.error` (line 123)**

The success rate failure uses `logger.error` but the event loss check uses `logger.warning`. Both represent assertion failures and should use the same severity for consistent log parsing.

## Verdict
NEEDS FIXES

Two critical issues (C1, C2) must be resolved before this test is CI-ready. The assertions exist in spirit but have no mechanism to fail a pipeline. The latency requirement is entirely unimplemented. Additionally, the single-threaded server (M2) will produce unreliable latency measurements under the intended load, making a latency assertion meaningless until the server can handle concurrent requests.
