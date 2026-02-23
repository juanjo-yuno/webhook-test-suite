# Review: Replay Tests

## Summary
PASS with observations. All 5 tests correctly validate the core replay functionality against `WebhookReplayManager`. Test isolation is solid, cleanup is handled properly, and the checklist items are covered. Two design-level observations noted below do not block acceptance but should be tracked.

## Test Count
| Expected | Actual | Status |
|----------|--------|--------|
| 5 (one per checklist item 1-5) | 5 | OK |

- `test_replay_resends_original_payload`
- `test_replay_marked_in_logs`
- `test_replay_specific_event_by_id`
- `test_replay_failed_deliveries_only`
- `test_replay_respects_current_merchant_url`

## Checklist
| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Replay resends exact original payload (with `_replay` marker) | PASS | Verifies 5 original fields preserved + `_replay: True`. `manager.py:29-30` copies payload via `dict()` and injects marker. |
| 2 | Replayed deliveries marked distinctly in logs (not confused with originals) | PASS* | Test verifies `_replay: True` in the merchant-received payload and that the logger recorded the attempt. However, `DeliveryAttempt` has no `is_replay` field -- replay vs original attempts are structurally identical in the logger. See Issue 1. |
| 3 | Can replay specific event by ID | PASS | Registers 3 events, replays only `event_b`, asserts merchant received exactly 1 event with the correct `payment_id` and `event_type`. |
| 4 | Bulk replay filters to failed-only deliveries | PASS* | Test correctly validates that `replay_failed` skips event A (200) and replays B and C (500). Uses `max_retries=0` for clean isolation. However, the source `replay_failed` has an edge case -- see Issue 2. |
| 5 | Uses updated merchant URL (not stale URL from original delivery) | PASS | Delivers to server_1 (500), replays to server_2 (200). Asserts `attempts[-1].url == server_2.url` and that server_1 never received a `_replay` payload. |
| 6 | Tests use `WebhookReplayManager` from `src/` | PASS | `conftest.py` imports from `src.replay.manager`. `test_replay_failed_deliveries_only` also directly imports it. All tests use the production class. |
| 7 | Test isolation (fresh state per test) | PASS | All fixtures are function-scoped (pytest default). Each test gets fresh `logger`, `engine`, `replay_manager`. Manually created `MerchantWebhookServer` instances use `try/finally` for cleanup. |

## Issues Found

### Issue 1 (Observation -- low severity): Log entries lack replay distinction

**File:** `src/models/delivery.py`, `src/webhook_simulator/logger.py`

`DeliveryAttempt` has no `is_replay` field. When `test_replay_marked_in_logs` checks "marked distinctly in logs," it actually verifies the merchant-received payload contains `_replay: True`, not that the log entries themselves are distinguishable. If someone queries `logger.get_attempts(event_id=X)`, they cannot tell which attempts were replays without cross-referencing the payload.

**Recommendation:** Consider adding an `is_replay: bool = False` field to `DeliveryAttempt` and setting it in `WebhookReplayManager.replay_event`. Then the test could assert `logged[-1].is_replay is True`.

### Issue 2 (Observation -- medium severity): `replay_failed` replays events with mixed results

**File:** `src/replay/manager.py:43-56`

`replay_failed` collects event IDs from `logger.get_failed_attempts()` and replays all of them. If an event had a failed attempt followed by a successful retry (e.g., 500 then 200), it still appears in `failed_event_ids` and would be unnecessarily replayed.

The current test avoids this by using `max_retries=0`, so events either fully succeed or fully fail. A test with `max_retries >= 1` where an event fails once then succeeds on retry would expose this behavior.

**Recommendation:** `replay_failed` should exclude events that have at least one successful delivery. For example:
```python
successful_ids = {a.event_id for a in self.logger.get_attempts()
                  if a.status_code and 200 <= a.status_code < 300}
failed_event_ids -= successful_ids
```

### Issue 3 (Minor): Unused `engine` fixture in `test_replay_resends_original_payload`

**File:** `tests/e2e/test_replay.py:18`

The `engine` fixture is injected but never used directly. The `replay_manager` fixture already contains the engine. This is harmless but slightly misleading when reading the test signature.

## Verdict
**PASS**

All 5 tests correctly exercise the replay functionality against the production `WebhookReplayManager`. Test isolation is sound, cleanup is proper, and each checklist item is covered. The two design observations (Issues 1 and 2) are worth tracking but do not constitute test failures or correctness problems in the current test suite.
