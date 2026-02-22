"""Retry logic using tenacity."""

from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def with_retry(max_attempts: int = 3, min_wait: int = 1, max_wait: int = 30):
    """Decorator factory for retrying functions with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )


# Pre-built decorators
retry_api_call = with_retry(max_attempts=3, min_wait=2, max_wait=60)
retry_http = with_retry(max_attempts=3, min_wait=1, max_wait=15)
