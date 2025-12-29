"""Rate limiting using token bucket algorithm."""
import time
from typing import Dict, Tuple
from collections import defaultdict
from fastapi import HTTPException, status
from app.cost.models import APIKey


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens (requests)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default: 1)

        Returns:
            True if tokens were consumed, False otherwise
        """
        now = time.time()
        # Refill tokens based on time elapsed
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_retry_after(self) -> float:
        """Calculate seconds until next token is available."""
        if self.tokens >= 1:
            return 0
        return (1 - self.tokens) / self.refill_rate


class RateLimiter:
    """Rate limiter that manages token buckets per API key."""

    def __init__(self):
        # Store token buckets per API key ID
        self.buckets: Dict[str, TokenBucket] = {}

    def _get_or_create_bucket(self, api_key: APIKey) -> TokenBucket:
        """Get or create a token bucket for an API key."""
        key_id = str(api_key.id)
        if key_id not in self.buckets:
            # Create bucket with capacity = rate_limit_per_minute
            # Refill rate = rate_limit_per_minute / 60 (tokens per second)
            capacity = api_key.rate_limit_per_minute
            refill_rate = capacity / 60.0
            self.buckets[key_id] = TokenBucket(capacity, refill_rate)
        return self.buckets[key_id]

    def check_rate_limit(self, api_key: APIKey) -> None:
        """
        Check if request should be rate limited.

        Args:
            api_key: API key record

        Raises:
            HTTPException: If rate limit is exceeded (429)
        """
        bucket = self._get_or_create_bucket(api_key)
        if not bucket.consume():
            retry_after = int(bucket.get_retry_after()) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )


# Global rate limiter instance
rate_limiter = RateLimiter()

