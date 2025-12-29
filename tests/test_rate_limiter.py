"""Tests for rate limiting."""
import pytest
import uuid
from app.auth.rate_limiter import RateLimiter, TokenBucket
from app.cost.models import APIKey


def test_token_bucket_consume():
    """Test token bucket consumption."""
    bucket = TokenBucket(capacity=10, refill_rate=1.0)
    assert bucket.consume() is True
    assert bucket.tokens == 9


def test_token_bucket_exhausted():
    """Test token bucket exhaustion."""
    bucket = TokenBucket(capacity=2, refill_rate=0.1)
    assert bucket.consume() is True
    assert bucket.consume() is True
    assert bucket.consume() is False  # Should be exhausted


def test_rate_limiter_check():
    """Test rate limiter with API key."""
    limiter = RateLimiter()
    api_key = APIKey(
        id=uuid.uuid4(),
        key_hash="test-hash",
        rate_limit_per_minute=60,
        is_active=True,
    )

    # Should allow requests within limit
    for _ in range(60):
        limiter.check_rate_limit(api_key)  # Should not raise

    # Should raise on 61st request
    with pytest.raises(Exception):  # Should raise HTTPException
        limiter.check_rate_limit(api_key)

