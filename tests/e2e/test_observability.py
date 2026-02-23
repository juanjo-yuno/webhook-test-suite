import time

import pytest

from src.observability.metrics import MetricsCollector
from src.observability.alerting import AlertManager


@pytest.mark.e2e
class TestObservabilityAlerts:
    """E2E tests for MetricsCollector + AlertManager working together."""

    def test_alert_fires_when_failure_rate_exceeds_10_percent(
        self, metrics, alert_manager
    ):
        """82% failure rate (9 failures / 11 total) must trigger an alert."""
        for _ in range(2):
            metrics.record_success()
        for _ in range(9):
            metrics.record_failure()

        alert = alert_manager.check()

        assert alert is not None
        assert alert["type"] == "webhook_failure_rate"
        assert alert["failure_rate"] == pytest.approx(9 / 11)
        assert alert["threshold"] == 0.10
        assert alert["total_deliveries"] == 11
        assert alert["failed_deliveries"] == 9
        assert isinstance(alert["message"], str)
        assert "81.8%" in alert["message"] or "failure rate" in alert["message"].lower()

    def test_no_alert_when_failure_rate_below_threshold(self, metrics, alert_manager):
        """5% failure rate (5/100) should not trigger an alert."""
        for _ in range(95):
            metrics.record_success()
        for _ in range(5):
            metrics.record_failure()

        alert = alert_manager.check()

        assert alert is None

    def test_alert_within_5_minute_window(self):
        """Entries older than the rolling window are pruned; rate resets to 0."""
        short_metrics = MetricsCollector(window_seconds=0.1)
        short_am = AlertManager(metrics=short_metrics, threshold=0.10)

        for _ in range(10):
            short_metrics.record_failure()

        time.sleep(0.2)

        alert = short_am.check()
        assert alert is None
        assert short_metrics.failure_rate() == 0.0

    def test_novapay_scenario_detected(self, metrics, alert_manager):
        """NovaPay 4-hour blackout: 100 consecutive failures, 0 successes.
        This is the scenario that would have prevented the $47K incident."""
        for _ in range(100):
            metrics.record_failure()

        alert = alert_manager.check()

        assert alert is not None
        assert alert["failure_rate"] == pytest.approx(1.0)
        assert alert["failed_deliveries"] == 100
        assert alert["total_deliveries"] == 100
        assert "100.0%" in alert["message"]

    def test_transient_failures_dont_trigger_alert(self, metrics, alert_manager):
        """3% failure rate (3/98) is below the 10% threshold -- no alert."""
        for _ in range(95):
            metrics.record_success()
        for _ in range(3):
            metrics.record_failure()

        alert = alert_manager.check()
        assert alert is None

    def test_alert_includes_failure_details(self, metrics, alert_manager):
        """Verify every required field and its type in the alert dict."""
        for _ in range(20):
            metrics.record_failure()

        alert = alert_manager.check()

        assert alert is not None
        assert alert["type"] == "webhook_failure_rate"
        assert isinstance(alert["failure_rate"], float)
        assert isinstance(alert["threshold"], float)
        assert isinstance(alert["total_deliveries"], int)
        assert isinstance(alert["failed_deliveries"], int)
        assert isinstance(alert["message"], str)
        assert len(alert["message"]) > 0

    def test_alert_callback_invoked(self):
        """Callback function receives the alert dict when alert fires."""
        collected = []
        m = MetricsCollector(window_seconds=300)
        am = AlertManager(metrics=m, threshold=0.10, callback=collected.append)

        for _ in range(10):
            m.record_failure()

        alert = am.check()

        assert alert is not None
        assert len(collected) == 1
        assert collected[0] is alert

    def test_fire_once_prevents_duplicate_alerts(self, metrics, alert_manager):
        """After first alert fires, subsequent check() returns None."""
        for _ in range(10):
            metrics.record_failure()

        first = alert_manager.check()
        assert first is not None

        second = alert_manager.check()
        assert second is None
