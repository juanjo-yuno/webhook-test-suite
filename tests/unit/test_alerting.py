import pytest

from src.observability.alerting import AlertManager
from src.observability.metrics import MetricsCollector


class TestAlertCheck:
    """Tests for AlertManager.check()."""

    @pytest.mark.unit
    def test_check_returns_alert_when_rate_exceeds_threshold(self, metrics, alert_manager):
        # Threshold is 0.10. Record 2 failures out of 3 total => 66.7%
        metrics.record_success()
        metrics.record_failure()
        metrics.record_failure()
        alert = alert_manager.check()
        assert alert is not None
        assert alert["type"] == "webhook_failure_rate"
        assert alert["failure_rate"] > alert_manager.threshold
        assert alert["total_deliveries"] == 3
        assert alert["failed_deliveries"] == 2

    @pytest.mark.unit
    def test_check_returns_none_when_rate_below_threshold(self, metrics, alert_manager):
        # Threshold is 0.10. Record 10 successes, 0 failures => 0%
        for _ in range(10):
            metrics.record_success()
        alert = alert_manager.check()
        assert alert is None

    @pytest.mark.unit
    def test_callback_is_invoked_on_alert(self):
        received = []
        mc = MetricsCollector(window_seconds=300)
        am = AlertManager(metrics=mc, threshold=0.10, callback=lambda a: received.append(a))
        mc.record_failure()
        mc.record_failure()
        am.check()
        assert len(received) == 1
        assert received[0]["type"] == "webhook_failure_rate"

    @pytest.mark.unit
    def test_custom_threshold_works(self):
        mc = MetricsCollector(window_seconds=300)
        am = AlertManager(metrics=mc, threshold=0.50)
        # 1 failure + 2 successes = 33% failure rate, below 50% threshold
        mc.record_failure()
        mc.record_success()
        mc.record_success()
        assert am.check() is None
        # Add more failures to exceed 50%
        mc.record_failure()
        mc.record_failure()
        # Now 3 failures / 5 total = 60% > 50%
        alert = am.check()
        assert alert is not None

    @pytest.mark.unit
    def test_fire_once_second_check_returns_none(self, metrics, alert_manager):
        metrics.record_failure()
        metrics.record_failure()
        first = alert_manager.check()
        assert first is not None
        second = alert_manager.check()
        assert second is None

    @pytest.mark.unit
    def test_reset_allows_refiring(self, metrics, alert_manager):
        metrics.record_failure()
        metrics.record_failure()
        first = alert_manager.check()
        assert first is not None
        # Second check without reset returns None
        assert alert_manager.check() is None
        # Reset and check again
        alert_manager.reset()
        refired = alert_manager.check()
        assert refired is not None
