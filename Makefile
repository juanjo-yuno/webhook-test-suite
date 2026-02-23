.PHONY: install test test-unit test-integration test-e2e test-load lint clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -m "not load"

test-unit:
	pytest tests/unit/ -m unit

test-integration:
	pytest tests/integration/ -m integration

test-e2e:
	pytest tests/e2e/ -m e2e

test-load:
	locust -f tests/load/locustfile.py --headless -u 50 -r 10 --run-time 30s --host http://127.0.0.1:8080

lint:
	python -m py_compile src/webhook_simulator/engine.py
	python -m py_compile src/merchant_receiver/server.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage dist build
