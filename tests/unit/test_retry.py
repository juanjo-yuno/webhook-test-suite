import pytest

from src.webhook_simulator.retry import RetryManager


class TestShouldRetry:
    """Tests for RetryManager.should_retry()."""

    @pytest.mark.unit
    @pytest.mark.parametrize("status_code", [500, 502, 503])
    def test_should_retry_true_for_5xx(self, retry_manager, status_code):
        assert retry_manager.should_retry(status_code) is True

    @pytest.mark.unit
    def test_should_retry_true_for_none_connection_error(self, retry_manager):
        assert retry_manager.should_retry(None) is True

    @pytest.mark.unit
    @pytest.mark.parametrize("status_code", [200, 201, 204])
    def test_should_retry_false_for_2xx(self, retry_manager, status_code):
        assert retry_manager.should_retry(status_code) is False

    @pytest.mark.unit
    @pytest.mark.parametrize("status_code", [400, 401, 404, 422])
    def test_should_retry_false_for_4xx_no_retry_codes(self, retry_manager, status_code):
        assert retry_manager.should_retry(status_code) is False

    @pytest.mark.unit
    def test_should_retry_false_for_429(self, retry_manager):
        """429 is not in NO_RETRY_CODES and not 5xx, so should_retry returns False."""
        assert retry_manager.should_retry(429) is False


class TestNextDelay:
    """Tests for RetryManager.next_delay()."""

    @pytest.mark.unit
    def test_next_delay_returns_correct_default_schedule_values(self, retry_manager):
        expected = [30, 300, 1800, 7200]
        for attempt, expected_delay in enumerate(expected):
            assert retry_manager.next_delay(attempt) == float(expected_delay)

    @pytest.mark.unit
    def test_next_delay_returns_last_value_when_attempt_exceeds_schedule(self, retry_manager):
        last_value = float(RetryManager.DEFAULT_SCHEDULE[-1])
        assert retry_manager.next_delay(10) == last_value
        assert retry_manager.next_delay(100) == last_value

    @pytest.mark.unit
    def test_next_delay_with_custom_schedule(self):
        rm = RetryManager(schedule=[1, 2, 3])
        assert rm.next_delay(0) == 1.0
        assert rm.next_delay(1) == 2.0
        assert rm.next_delay(2) == 3.0
        assert rm.next_delay(5) == 3.0  # clamps to last


class TestHasAttemptsRemaining:
    """Tests for RetryManager.has_attempts_remaining()."""

    @pytest.mark.unit
    def test_has_attempts_remaining_true_when_under_max(self, retry_manager):
        # Default max_retries = len(DEFAULT_SCHEDULE) = 4
        assert retry_manager.has_attempts_remaining(0) is True
        assert retry_manager.has_attempts_remaining(3) is True

    @pytest.mark.unit
    def test_has_attempts_remaining_false_when_at_or_over_max(self, retry_manager):
        max_retries = len(RetryManager.DEFAULT_SCHEDULE)  # 4
        assert retry_manager.has_attempts_remaining(max_retries) is False
        assert retry_manager.has_attempts_remaining(max_retries + 1) is False


class TestCustomConfiguration:
    """Tests for RetryManager with custom schedule/max_retries."""

    @pytest.mark.unit
    def test_custom_schedule_overrides_default(self):
        custom = [10, 20, 30]
        rm = RetryManager(schedule=custom)
        assert rm.schedule == custom
        assert rm.next_delay(0) == 10.0

    @pytest.mark.unit
    def test_custom_max_retries_overrides_default(self):
        rm = RetryManager(max_retries=2)
        assert rm.max_retries == 2
        assert rm.has_attempts_remaining(1) is True
        assert rm.has_attempts_remaining(2) is False

    @pytest.mark.unit
    def test_max_retries_zero_means_no_retries(self):
        rm = RetryManager(max_retries=0)
        assert rm.has_attempts_remaining(0) is False


class TestDefaults:
    """Tests for RetryManager constructor defaults."""

    @pytest.mark.unit
    def test_default_schedule_values(self):
        assert RetryManager.DEFAULT_SCHEDULE == [30, 300, 1800, 7200]

    @pytest.mark.unit
    def test_constructor_defaults(self):
        rm = RetryManager()
        assert rm.schedule == RetryManager.DEFAULT_SCHEDULE
        assert rm.max_retries == len(RetryManager.DEFAULT_SCHEDULE)
