import pytest

from src.webhook_simulator.signer import WebhookSigner
from src.webhook_simulator.retry import RetryManager
from src.webhook_simulator.logger import DeliveryLogger
from src.webhook_simulator.engine import WebhookDeliveryEngine
from src.merchant_receiver.server import MerchantWebhookServer
from src.observability.metrics import MetricsCollector
from src.observability.alerting import AlertManager
from src.replay.manager import WebhookReplayManager
from src.utils.factories import PaymentFactory, WebhookFactory


WEBHOOK_SECRET = "test-secret-key-for-hmac"


@pytest.fixture
def webhook_secret():
    return WEBHOOK_SECRET


@pytest.fixture
def signer():
    return WebhookSigner(WEBHOOK_SECRET)


@pytest.fixture
def retry_manager():
    return RetryManager()


@pytest.fixture
def logger():
    return DeliveryLogger()


@pytest.fixture
def engine(signer, retry_manager, logger):
    return WebhookDeliveryEngine(
        signer=signer,
        retry_manager=retry_manager,
        logger=logger,
        timeout_seconds=5,
    )


@pytest.fixture
def merchant_server():
    server = MerchantWebhookServer(secret=WEBHOOK_SECRET)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def merchant_server_no_auth():
    """Merchant server without signature verification."""
    server = MerchantWebhookServer()
    server.start()
    yield server
    server.stop()


@pytest.fixture
def metrics():
    return MetricsCollector(window_seconds=300)


@pytest.fixture
def alert_manager(metrics):
    return AlertManager(metrics=metrics, threshold=0.10)


@pytest.fixture
def replay_manager(engine, logger):
    return WebhookReplayManager(engine=engine, logger=logger)


@pytest.fixture
def payment_factory():
    return PaymentFactory


@pytest.fixture
def webhook_factory():
    return WebhookFactory
