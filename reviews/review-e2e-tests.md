# Review: E2E Core Tests

## Summary
PASS (with minor observations)

## Test Count
| File | Expected | Actual | Status |
|------|:--------:|:------:|:------:|
| test_full_payment_flow.py | ~6 | 6 | OK |
| test_idempotency.py | ~5 | 5 | OK |
| test_signature_verify.py | ~5 | 5 | OK |
| test_out_of_order.py | ~4 | 4 | OK |
| test_malformed_payload.py | ~5 | 5 | OK |
| **Total** | **~25** | **25** | **OK** |

## Checklist
| # | Check | Status | Notes |
|---|-------|:------:|-------|
| 1 | Full payment lifecycle tested (auth -> capture -> settle) | PASS | `test_full_lifecycle_auth_capture_settle` sends auth, capture, settle in sequence for the same `payment_id` and verifies order + count. Individual event types (auth, capture, decline, settle, chargeback) each have their own test. |
| 2 | Idempotency: duplicate webhook -> single business action | PASS | `test_duplicate_webhook_processed_once` delivers the same event twice and asserts `get_processed_count() == 1`. Triple delivery also covered. Different events for same payment correctly processed as separate. |
| 3 | Signature: HMAC verified, tampered payloads rejected with 401 | PASS | Five scenarios: valid (200), invalid sig (401), missing sig (401), tampered payload (401), wrong secret (401). All assert `get_processed_count() == 0` for rejection cases. |
| 4 | Out-of-order: capture before auth handled without crash | PASS | `test_capture_before_auth_both_received` delivers capture then auth and asserts both return 200. Settle-before-capture also covered. Full reverse order (chargeback, settle, auth, capture) tested in `test_all_events_delivered_even_if_out_of_order`. |
| 5 | Malformed: missing fields -> 400, not 500 | PASS | Missing `payment_id` -> 400, missing `event_type` -> 400, invalid amount -> 400, empty JSON `{}` -> 400, non-JSON body -> 400. Error messages verified for content (e.g., field name in error string). |
| 6 | Tests use real simulator + receiver (not unit-level mocks) | PASS | `WebhookDeliveryEngine.deliver()` makes real `requests.post()` calls. `MerchantWebhookServer` runs a real `HTTPServer` on localhost with a random port. No mocking or patching anywhere. |
| 7 | Test isolation: each test gets fresh server/engine state | PASS | All fixtures (`engine`, `merchant_server`, `signer`, `retry_manager`, `logger`) use default function scope. `idempotent_server` and `sig_server` are function-scoped local fixtures with explicit `start()`/`stop()` in yield. Each test gets a clean server with empty `received_events` and `processed_event_ids`. |
| 8 | Test count per file matches expected | PASS | See table above. |

## Issues Found

### Issue 1: Server validates payload fields before verifying signature
- **File**: `/Users/juanjo/webhook-test-suite/src/merchant_receiver/server.py` (lines 34-67)
- **Severity**: Minor
- **Problem**: The server's request handler validates required fields and amount (lines 34-51) before checking the HMAC signature (lines 54-67). This means all five malformed payload tests get their 400 response before the signature is ever checked. An unauthenticated request with a malformed body receives a 400 (leaking validation rules) instead of a 401. This is a defense-in-depth concern: in production, signature verification should run first to reject unauthenticated requests before revealing anything about the payload schema.
- **Impact on tests**: The malformed payload tests pass correctly, but they do not exercise the full validation pipeline (signature + field validation). If someone later fixes the server to check signature first, `test_completely_malformed_json_returns_400` would break because it sends no `X-Webhook-Signature` header.
- **Fix instruction**: In `server.py`, move the signature verification block (lines 54-67) above the required fields validation (lines 34-51). Then in `test_malformed_payload.py`, update `test_completely_malformed_json_returns_400` to either: (a) expect 401 instead of 400 since the body cannot be signed, or (b) use the `merchant_server_no_auth` fixture (already defined in conftest) so signature verification is not a factor.

### Issue 2: `test_completely_malformed_json_returns_400` omits signature header
- **File**: `/Users/juanjo/webhook-test-suite/tests/e2e/test_malformed_payload.py` (line 115-129)
- **Severity**: Minor
- **Problem**: This test sends `"this is not json {{{"` without an `X-Webhook-Signature` header. The `merchant_server` fixture has signature verification enabled (`secret=WEBHOOK_SECRET`). The test only passes because JSON parsing fails (line 24-30 in server.py) before the signature check is reached. If validation order changes in the server, this test would return 401 instead of 400. The other four malformed tests include a valid signature; this one does not.
- **Fix instruction**: Either add a comment documenting the dependency on validation order, or use the `merchant_server_no_auth` fixture for this specific test, or send a dummy signature header for consistency with the other malformed tests.

### Issue 3: `webhook_factory` fixture returns a class, not an instance
- **File**: `/Users/juanjo/webhook-test-suite/tests/conftest.py` (lines 85-87)
- **Severity**: Minor
- **Problem**: The `webhook_factory` fixture returns `WebhookFactory` (the class itself). Tests call `webhook_factory.create_event(...)` which works because `create_event` is a `@staticmethod`. Same pattern for `payment_factory`. While functionally correct, this is unconventional -- fixtures typically return instances. A reader unfamiliar with the code might expect `webhook_factory` to be an instance and be confused when they see no `()` instantiation.
- **Fix instruction**: No functional change needed. Either (a) add a docstring to the fixture explaining it returns the class for static method access, or (b) change to `return WebhookFactory()` and keep `create_event` as a regular method. Option (a) is lower risk.

## Verdict
PASS -- 3 minor issues, 0 critical/major.

All 25 tests cover the required scenarios. Tests use real HTTP servers (not mocks), each test gets fresh state via function-scoped fixtures, and the assertions check both status codes and payload content. The three minor issues are about validation order coupling and code style, none of which affect test correctness under the current server implementation.
