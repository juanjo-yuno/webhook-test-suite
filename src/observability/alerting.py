from src.observability.metrics import MetricsCollector


class AlertManager:
    """Monitors MetricsCollector and fires alerts when thresholds are exceeded."""

    def __init__(
        self,
        metrics: MetricsCollector,
        threshold: float = 0.10,
        callback=None,
    ):
        self.metrics = metrics
        self.threshold = threshold
        self.callback = callback
        self._fired = False
        self._alerts: list[dict] = []

    def check(self) -> dict | None:
        """Check if failure rate exceeds threshold. Returns alert dict or None."""
        rate = self.metrics.failure_rate()
        total = self.metrics.total_in_window()
        failures = self.metrics.failure_count_in_window()

        if total == 0:
            return None

        if rate > self.threshold:
            if self._fired:
                return None  # Already fired, don't repeat

            alert = {
                "type": "webhook_failure_rate",
                "failure_rate": rate,
                "threshold": self.threshold,
                "total_deliveries": total,
                "failed_deliveries": failures,
                "message": (
                    f"Webhook failure rate {rate:.1%} exceeds "
                    f"threshold {self.threshold:.1%} "
                    f"({failures}/{total} deliveries failed)"
                ),
            }
            self._fired = True
            self._alerts.append(alert)

            if self.callback:
                self.callback(alert)

            return alert

        # Rate is back below threshold, reset fire-once
        self._fired = False
        return None

    def get_alerts(self) -> list[dict]:
        return list(self._alerts)

    def reset(self) -> None:
        self._fired = False
        self._alerts.clear()
