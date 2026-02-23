class RetryManager:
    """Manages retry decisions and backoff scheduling for webhook delivery."""

    DEFAULT_SCHEDULE = [30, 300, 1800, 7200]  # 30s, 5m, 30m, 2h

    # Status codes that should NOT trigger retries
    NO_RETRY_CODES = {400, 401, 404, 422}

    def __init__(self, schedule: list[int] | None = None, max_retries: int | None = None):
        self.schedule = schedule or self.DEFAULT_SCHEDULE
        self.max_retries = max_retries if max_retries is not None else len(self.schedule)

    def should_retry(self, status_code: int | None) -> bool:
        """Determine if a delivery should be retried based on status code.

        Returns True for:
        - None (connection error / timeout)
        - 5xx server errors
        Returns False for:
        - 2xx success
        - 4xx client errors
        """
        if status_code is None:
            return True
        if 200 <= status_code < 300:
            return False
        if status_code in self.NO_RETRY_CODES:
            return False
        if status_code >= 500:
            return True
        return False

    def next_delay(self, attempt: int) -> float:
        """Get the delay in seconds before the next retry attempt (0-indexed)."""
        if attempt >= len(self.schedule):
            return self.schedule[-1]
        return float(self.schedule[attempt])

    def has_attempts_remaining(self, attempt: int) -> bool:
        """Check if more retry attempts are allowed."""
        return attempt < self.max_retries
