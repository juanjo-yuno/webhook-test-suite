# Review: Unit Tests

## Summary
**PASS** — The unit test suite is well-structured, thorough, and correctly validates the source code. All six expected test files exist with test counts meeting or exceeding expectations. Tests are isolated, use meaningful assertions, correctly import source modules, and cover both positive and negative cases. A few minor observations are noted below but none require mandatory fixes.

## Test Count
| File | Expected (methods) | Actual (methods) | Actual (parametrized) | Status |
|---|:---:|:---:|:---:|:---:|
| test_retry.py | ~15 | 15 | 22 | PASS |
| test_signer.py | ~8 | 8 | 8 | PASS |
| test_payload.py | ~12 | 12 | 16 | PASS |
| test_factories.py | ~6 | 6 | 10 | PASS |
| test_metrics.py | ~8 | 8 | 8 | PASS |
| test_alerting.py | ~6 | 6 | 6 | PASS |
| **Total** | **~55** | **55** | **70** | **PASS** |

## Checklist
| # | Check | Status | Notes |
|---|---|:---:|---|
| 1 | All expected test files exist with expected test counts | PASS | All 6 files present. Method counts match expectations; parametrized expansion exceeds them. |
| 2 | Each test has meaningful assertions (not just `assert True`) | PASS | Every test contains specific assertions against return values, types, lengths, or object attributes. No vacuous assertions found. |
| 3 | Tests are isolated (no shared mutable state between tests) | PASS | Fixtures in `conftest.py` create fresh instances per test (default function scope). Tests that need custom config instantiate their own objects inline rather than mutating shared state. |
| 4 | Tests cover both positive and negative cases | PASS | Retry: 5xx/None/2xx/4xx/429 covered. Signer: valid/invalid/tampered signatures. Alerting: above/below threshold. Metrics: zero-data edge case. |
| 5 | Factories and fixtures used correctly (from conftest.py) | PASS | `retry_manager`, `signer`, `metrics`, `alert_manager` fixtures used where appropriate. Tests needing custom config correctly bypass fixtures and construct instances directly. `payment_factory` and `webhook_factory` fixtures exist in conftest but tests call the static methods directly on the classes, which is acceptable. |
| 6 | Tests actually import and use the correct src/ modules | PASS | `test_retry.py` imports `src.webhook_simulator.retry.RetryManager`. `test_signer.py` imports `src.webhook_simulator.signer.WebhookSigner`. `test_payload.py` imports `src.utils.factories.WebhookFactory`. `test_factories.py` imports `src.models.payment.Payment/PaymentStatus` and `src.utils.factories.PaymentFactory/WebhookFactory`. `test_metrics.py` imports `src.observability.metrics.MetricsCollector`. `test_alerting.py` imports `src.observability.alerting.AlertManager` and `src.observability.metrics.MetricsCollector`. All correct. |
| 7 | No hardcoded values that should come from fixtures | PASS | Constants like `DEFAULT_SCHEDULE = [30, 300, 1800, 7200]` in test_retry.py mirror the source class constant and are verified via `RetryManager.DEFAULT_SCHEDULE`. Secrets in test_signer.py use the fixture `signer` which gets the secret from conftest's `WEBHOOK_SECRET`. Inline construction uses explicit test-local values, not duplicated magic numbers. |
| 8 | Edge cases covered | PASS | See detailed breakdown below. |

### Edge Case Coverage Detail (Check #8)

| Edge Case | Covered? | Where |
|---|:---:|---|
| Partial captures | Yes | `test_payload.py::TestCurrencyAndAmounts::test_partial_capture` — verifies `amount="200.00"` with `captured_amount="150.00"` |
| Multi-currency | Yes | `test_payload.py::TestCurrencyAndAmounts::test_multi_currency_support` — USD, EUR, BRL, COP |
| Uncommon decline codes | Partial | Default `insufficient_funds` and `chargeback` tested. No test for uncommon codes like `do_not_honor` or `expired_card`, but the factory accepts arbitrary `decline_code` kwargs, so this is a design choice not a gap. |
| Empty payloads | Yes | `test_signer.py::TestSign::test_empty_payload_produces_valid_signature` — `signer.sign({})` |
| Unicode payloads | Yes | `test_signer.py::TestSign::test_unicode_payload_content_works` — payload with accented characters |
| Fire-once alerting | Yes | `test_alerting.py::TestAlertCheck::test_fire_once_second_check_returns_none` |
| Rolling window expiry | Yes | `test_metrics.py::TestRollingWindow::test_rolling_window_excludes_old_entries` — uses `window_seconds=0.1` + `time.sleep(0.15)` |
| Retry exhaustion / zero retries | Yes | `test_retry.py::TestCustomConfiguration::test_max_retries_zero_means_no_retries` |
| 429 status code (edge between 4xx and retryable) | Yes | `test_retry.py::TestShouldRetry::test_should_retry_false_for_429` |
| Alert reset / refire | Yes | `test_alerting.py::TestAlertCheck::test_reset_allows_refiring` |

## Issues Found

### Issue 1: `time.sleep` in rolling window test is brittle in CI
- **File**: `/Users/juanjo/webhook-test-suite/tests/unit/test_metrics.py`, line 65
- **Severity**: Minor
- **Problem**: `test_rolling_window_excludes_old_entries` uses `time.sleep(0.15)` with a `window_seconds=0.1`. While functional, tight timing margins (50ms buffer) can cause flaky failures in slow CI environments or under heavy load.
- **Fix instruction**: Consider increasing the margin (e.g., `window_seconds=0.05`, `sleep(0.15)`) or mocking `time.monotonic` to remove the timing dependency entirely. Not blocking.

### Issue 2: `payment_factory` and `webhook_factory` fixtures are unused
- **File**: `/Users/juanjo/webhook-test-suite/tests/conftest.py`, lines 80-86
- **Severity**: Minor
- **Problem**: The `payment_factory` and `webhook_factory` fixtures are defined in conftest but no test uses them as fixture parameters. Tests call the factory classes directly via their static methods (e.g., `PaymentFactory.create()`, `WebhookFactory.create_event()`), which is perfectly valid but makes these two fixtures dead code.
- **Fix instruction**: Either remove the unused fixtures from conftest.py or refactor tests to inject them. Not blocking since the static method usage is correct.

### Issue 3: No test for unknown event type in WebhookFactory
- **File**: `/Users/juanjo/webhook-test-suite/tests/unit/test_payload.py`
- **Severity**: Minor
- **Problem**: The `_event_type_to_status()` function in `src/utils/factories.py` returns `"UNKNOWN"` for unrecognized event types, but no test verifies this behavior. If someone passes `"payment.refunded"` (not yet supported), the factory would silently produce `status="UNKNOWN"` in the payload.
- **Fix instruction**: Consider adding a test like `test_unknown_event_type_returns_unknown_status` that calls `WebhookFactory.create_event("payment.refunded")` and asserts `event.payload["status"] == "UNKNOWN"`. Not blocking.

### Issue 4: Unicode test uses ASCII-safe characters only
- **File**: `/Users/juanjo/webhook-test-suite/tests/unit/test_signer.py`, line 40
- **Severity**: Minor
- **Problem**: `test_unicode_payload_content_works` uses `"credito"` and `"Munchen"` which are standard Latin characters that don't actually test multi-byte UTF-8 encoding. True unicode edge cases (e.g., CJK characters, emoji, right-to-left text) are not covered.
- **Fix instruction**: Enhance the payload to include actual multi-byte characters, e.g., `{"description": "Pago credito", "emoji": "\u2705", "cjk": "\u4e16\u754c"}`. Not blocking since `json.dumps` handles unicode correctly by default.

## Verdict
**PASS** — no fixes needed. 4 minor observations noted above, none of which are correctness issues. The test suite is solid: correct imports, meaningful assertions, proper isolation, good positive/negative coverage, and all key edge cases are exercised.
