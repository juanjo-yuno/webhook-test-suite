import time

import pytest

from src.observability.metrics import MetricsCollector


class TestRecordAndCounts:
    """Tests for recording successes/failures and counting them."""

    @pytest.mark.unit
    def test_record_success_increments(self, metrics):
        metrics.record_success()
        metrics.record_success()
        assert metrics.success_count_in_window() == 2

    @pytest.mark.unit
    def test_record_failure_increments(self, metrics):
        metrics.record_failure()
        metrics.record_failure()
        metrics.record_failure()
        assert metrics.failure_count_in_window() == 3

    @pytest.mark.unit
    def test_total_in_window_counts_both(self, metrics):
        metrics.record_success()
        metrics.record_success()
        metrics.record_failure()
        assert metrics.total_in_window() == 3

    @pytest.mark.unit
    def test_success_count_and_failure_count_in_window(self, metrics):
        metrics.record_success()
        metrics.record_failure()
        metrics.record_failure()
        assert metrics.success_count_in_window() == 1
        assert metrics.failure_count_in_window() == 2


class TestFailureRate:
    """Tests for failure_rate computation."""

    @pytest.mark.unit
    def test_failure_rate_returns_correct_ratio(self, metrics):
        metrics.record_success()
        metrics.record_failure()
        # 1 failure out of 2 total = 0.5
        assert metrics.failure_rate() == pytest.approx(0.5)

    @pytest.mark.unit
    def test_failure_rate_returns_zero_when_empty(self, metrics):
        assert metrics.failure_rate() == 0.0


class TestRollingWindow:
    """Tests for rolling window expiry."""

    @pytest.mark.unit
    def test_rolling_window_excludes_old_entries(self):
        mc = MetricsCollector(window_seconds=0.1)
        mc.record_success()
        mc.record_failure()
        assert mc.total_in_window() == 2
        # Wait for entries to expire
        time.sleep(0.15)
        assert mc.total_in_window() == 0
        assert mc.failure_rate() == 0.0


class TestReset:
    """Tests for reset()."""

    @pytest.mark.unit
    def test_reset_clears_all_data(self, metrics):
        metrics.record_success()
        metrics.record_success()
        metrics.record_failure()
        assert metrics.total_in_window() == 3
        metrics.reset()
        assert metrics.total_in_window() == 0
        assert metrics.failure_rate() == 0.0
        assert metrics.success_count_in_window() == 0
        assert metrics.failure_count_in_window() == 0
