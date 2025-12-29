"""Prometheus metrics collection."""
from prometheus_client import Counter, Histogram, Gauge
from typing import Optional


# Request counter with labels: api_key, provider, status
request_count = Counter(
    "llm_gateway_requests_total",
    "Total number of requests",
    ["api_key_id", "provider", "status"],
)

# Error counter with labels: api_key, provider, error_type
error_count = Counter(
    "llm_gateway_errors_total",
    "Total number of errors",
    ["api_key_id", "provider", "error_type"],
)

# Fallback counter with labels: api_key, from_provider, to_provider
fallback_count = Counter(
    "llm_gateway_fallbacks_total",
    "Total number of fallbacks",
    ["api_key_id", "from_provider", "to_provider"],
)

# Cost counter with labels: api_key, provider, model
cost_total = Counter(
    "llm_gateway_cost_total",
    "Total cost in USD",
    ["api_key_id", "provider", "model"],
)

# Latency histogram with labels: api_key, provider
latency_histogram = Histogram(
    "llm_gateway_latency_seconds",
    "Request latency in seconds",
    ["api_key_id", "provider"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)


def record_request(api_key_id: str, provider: str, status: str = "success"):
    """Record a request."""
    request_count.labels(
        api_key_id=api_key_id,
        provider=provider,
        status=status,
    ).inc()


def record_error(api_key_id: str, provider: str, error_type: str):
    """Record an error."""
    error_count.labels(
        api_key_id=api_key_id,
        provider=provider,
        error_type=error_type,
    ).inc()


def record_fallback(api_key_id: str, from_provider: str, to_provider: str):
    """Record a fallback."""
    fallback_count.labels(
        api_key_id=api_key_id,
        from_provider=from_provider,
        to_provider=to_provider,
    ).inc()


def record_cost(api_key_id: str, provider: str, model: str, cost_usd: float):
    """Record cost."""
    cost_total.labels(
        api_key_id=api_key_id,
        provider=provider,
        model=model,
    ).inc(cost_usd)


def record_latency(api_key_id: str, provider: str, latency_seconds: float):
    """Record latency."""
    latency_histogram.labels(
        api_key_id=api_key_id,
        provider=provider,
    ).observe(latency_seconds)

