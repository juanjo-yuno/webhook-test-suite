# NovaPay Webhook Test Suite

Automated test suite for validating webhook delivery, retry logic, signature verification, observability, and replay capabilities for the NovaPay payment platform.

## Prerequisites

- Python 3.12+
- pip

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

### Using Make

```bash
make test              # All tests (except load)
make test-unit         # Unit tests only
make test-integration  # Integration tests
make test-e2e          # E2E tests
make test-load         # Load tests (Locust headless, 50 users, 30s)
```

### Using pytest directly

```bash
pytest tests/ -v                          # All tests
pytest tests/unit/ -m unit -v             # Unit tests
pytest tests/integration/ -m integration  # Integration tests
pytest tests/e2e/ -m e2e                  # E2E tests
pytest tests/ -m "not load" --tb=short    # All except load
```

## Project Structure

```
webhook-test-suite/
├── src/
│   ├── models/
│   │   ├── delivery.py          # DeliveryAttempt, DeliveryStatus
│   │   ├── payment.py           # Payment, PaymentStatus
│   │   └── webhook.py           # WebhookEvent, WebhookPayload
│   ├── merchant_receiver/
│   │   └── server.py            # MerchantWebhookServer (threaded HTTP)
│   ├── webhook_simulator/
│   │   ├── engine.py            # WebhookDeliveryEngine (deliver + retry)
│   │   ├── retry.py             # RetryManager (backoff schedule)
│   │   ├── signer.py            # WebhookSigner (HMAC-SHA256)
│   │   └── logger.py            # DeliveryLogger (thread-safe)
│   ├── observability/
│   │   ├── metrics.py           # MetricsCollector (rolling window)
│   │   └── alerting.py          # AlertManager (fire-once alerts)
│   ├── replay/
│   │   └── manager.py           # WebhookReplayManager
│   └── utils/
│       ├── crypto.py            # HMAC-SHA256 sign/verify
│       └── factories.py         # PaymentFactory, WebhookFactory
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── unit/                    # Unit tests (~55)
│   ├── integration/             # Integration tests (~38)
│   ├── e2e/                     # End-to-end tests (~36)
│   └── load/                    # Load tests (Locust)
├── docs/
│   ├── README.md                # This file
│   └── TEST_STRATEGY.md         # Test strategy document
├── Makefile
└── pyproject.toml
```

## Load Testing

Load tests use [Locust](https://locust.io/) to simulate concurrent webhook delivery.

### Headless mode (CI-friendly)

```bash
make test-load
```

This runs 50 concurrent users with a spawn rate of 10 users/second for 30 seconds against `http://127.0.0.1:8080`.

### Web UI mode

```bash
locust -f tests/load/locustfile.py --host http://127.0.0.1:8080
```

Then open http://localhost:8089 in your browser to configure and monitor the load test interactively.

### Custom parameters

```bash
locust -f tests/load/locustfile.py --headless -u 100 -r 20 --run-time 60s --host http://127.0.0.1:8080
```

- `-u`: Number of concurrent users
- `-r`: Spawn rate (users per second)
- `--run-time`: Test duration
- `--host`: Target server URL

## CI/CD

Tests run automatically on every push and pull request to `main` via GitHub Actions. The CI pipeline runs four parallel jobs:

1. **lint** - Syntax validation
2. **unit** - Unit tests with coverage reporting
3. **integration** - Integration tests
4. **e2e** - End-to-end tests

See `.github/workflows/test.yml` for the full configuration.
