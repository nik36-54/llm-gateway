# Complete Usage Guide - LLM Gateway

This guide explains how to use all features of the LLM Gateway, including cost attribution, failure handling, and observability.

## Table of Contents

1. [Cost Attribution](#cost-attribution)
2. [Production Failure Handling](#production-failure-handling)
3. [Observability & Metrics](#observability--metrics)
4. [How to Use Each Feature](#how-to-use-each-feature)

---

## Cost Attribution

### Data Collected Per Request

Every API request automatically collects and stores the following data:

| Field | Description | Example |
|-------|-------------|---------|
| `tokens_in` | Input tokens used | 150 |
| `tokens_out` | Output tokens generated | 75 |
| `cost_usd` | Cost in USD (calculated automatically) | 0.000375 |
| `provider` | Provider used (openai, deepseek, huggingface) | "openai" |
| `model` | Specific model used | "gpt-3.5-turbo" |
| `api_key` | API key that made the request (via foreign key) | UUID reference |

### How It Works

1. **Automatic Collection**: When you make a request to `/v1/chat/completions`, the gateway automatically:
   - Captures token usage from the provider response
   - Calculates cost based on provider pricing tables
   - Stores all data in the `cost_records` database table

2. **Cost Calculation**: Costs are calculated using pricing tables defined in `app/cost/tracker.py`:
   - OpenAI GPT-3.5: $0.0015/1K input, $0.002/1K output
   - OpenAI GPT-4: $0.03/1K input, $0.06/1K output
   - DeepSeek: $0.00014/1K input, $0.00028/1K output
   - HuggingFace: Free (all models)

3. **Storage**: All cost data is persisted to PostgreSQL database immediately after each request.

### Viewing Cost Data

**Option 1: In API Response**
Every chat completion response includes the cost:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'

# Response includes:
{
  "cost_usd": 0.00025,
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  },
  "provider": "openai"
}
```

**Option 2: Cost Summary Endpoint**
Get aggregated cost data:

```bash
# Get all-time summary
curl -X GET "http://localhost:8000/v1/costs" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Filter by date range
curl -X GET "http://localhost:8000/v1/costs?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Filter by provider
curl -X GET "http://localhost:8000/v1/costs?provider=openai" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Option 3: Detailed Records**
Get individual cost records:

```bash
# Get last 50 records
curl -X GET "http://localhost:8000/v1/costs/records?limit=50" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Get records for specific provider
curl -X GET "http://localhost:8000/v1/costs/records?provider=deepseek&limit=20" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Aggregating Costs

The `/v1/costs` endpoint provides automatic aggregation:

**By API Key**:
```json
{
  "by_api_key": [
    {
      "api_key_name": "customer-acme",
      "total_cost_usd": 12.45,
      "request_count": 5000,
      "total_tokens": 150000
    }
  ]
}
```

**By Provider**:
```json
{
  "by_provider": [
    {
      "provider": "openai",
      "total_cost_usd": 10.00,
      "request_count": 4000,
      "avg_latency_ms": 1200
    },
    {
      "provider": "deepseek",
      "total_cost_usd": 2.45,
      "request_count": 1000,
      "avg_latency_ms": 1500
    }
  ]
}
```

**By Model**:
```json
{
  "by_model": [
    {
      "model": "gpt-3.5-turbo",
      "total_cost_usd": 8.50,
      "request_count": 3500
    },
    {
      "model": "gpt-4",
      "total_cost_usd": 1.50,
      "request_count": 500
    }
  ]
}
```

---

## Production Failure Handling

### Timeout Protection

All provider calls have configurable timeouts (default: 30 seconds).

**Configuration**:
```bash
# In .env file
PROVIDER_TIMEOUT=30  # seconds
```

**What Happens**:
- If a provider doesn't respond within the timeout, a `ProviderTimeoutError` is raised
- The system automatically falls back to the next provider in the chain
- The timeout is logged and tracked in metrics

**Example**:
```python
# If OpenAI times out, system automatically tries DeepSeek, then HuggingFace
# No manual intervention needed
```

### Retry with Exponential Backoff

The system includes retry logic with exponential backoff (implemented in `app/utils/retry.py`).

**Configuration**:
- Max attempts: 3
- Initial delay: 1.0 second
- Exponential base: 2.0
- Max delay: 10.0 seconds

**How It Works**:
1. First attempt fails → Wait 1s → Retry
2. Second attempt fails → Wait 2s → Retry
3. Third attempt fails → Wait 4s → Retry
4. All attempts exhausted → Fallback to next provider

### Fallback Chain

The system maintains a fallback chain for each request:

**Default Chain**: OpenAI → DeepSeek → HuggingFace

**What Happens on Failure**:
1. Primary provider selected based on routing rules
2. If primary fails → Try secondary provider (0.5s delay)
3. If secondary fails → Try tertiary provider (0.5s delay)
4. If all fail → Return error to client

**Failure Scenarios Handled**:

1. **Provider Timeout**:
   - Exception: `ProviderTimeoutError`
   - Action: Immediate fallback to next provider
   - Tracked: In metrics as timeout error

2. **Provider Error Response**:
   - Exception: `ProviderError`
   - Action: Fallback to next provider
   - Tracked: In metrics with error type

3. **Rate Limit Exceeded**:
   - Exception: `ProviderRateLimitError`
   - Action: Fallback to next provider (avoids rate limit)
   - Tracked: In metrics as rate limit error

### Graceful Error Handling

All errors are handled gracefully:

```python
# User receives friendly error messages, not stack traces
{
  "detail": "LLM provider error: OpenAI rate limit exceeded"
}

# System continues to function (fallback happens automatically)
# No crashes, no downtime
```

### Monitoring Failures

**In Logs**:
```bash
# Check for failures
docker-compose logs app | grep -i error

# Check for fallbacks
docker-compose logs app | grep -i fallback
```

**In Metrics**:
```bash
# Check error rate
curl http://localhost:8000/metrics | grep llm_gateway_errors_total

# Check fallback count
curl http://localhost:8000/metrics | grep llm_gateway_fallbacks_total
```

---

## Observability & Metrics

### Prometheus Metrics Endpoint

**Endpoint**: `GET /metrics`

**Access**:
```bash
curl http://localhost:8000/metrics
```

### Available Metrics

#### 1. Request Count (`llm_gateway_requests_total`)

**Type**: Counter  
**Labels**: `api_key_id`, `provider`, `status`

**Example**:
```
llm_gateway_requests_total{api_key_id="123",provider="openai",status="success"} 1500
llm_gateway_requests_total{api_key_id="123",provider="openai",status="failure"} 5
```

**Usage in Prometheus**:
```promql
# Total requests
sum(llm_gateway_requests_total)

# Requests per provider
sum by (provider) (llm_gateway_requests_total)

# Success rate
sum(rate(llm_gateway_requests_total{status="success"}[5m])) / sum(rate(llm_gateway_requests_total[5m]))
```

#### 2. Error Rate (`llm_gateway_errors_total`)

**Type**: Counter  
**Labels**: `api_key_id`, `provider`, `error_type`

**Example**:
```
llm_gateway_errors_total{api_key_id="123",provider="openai",error_type="ProviderTimeoutError"} 3
llm_gateway_errors_total{api_key_id="123",provider="openai",error_type="ProviderRateLimitError"} 2
```

**Usage in Prometheus**:
```promql
# Error rate per second
rate(llm_gateway_errors_total[5m])

# Errors by type
sum by (error_type) (llm_gateway_errors_total)

# Error rate percentage
sum(rate(llm_gateway_errors_total[5m])) / sum(rate(llm_gateway_requests_total[5m])) * 100
```

#### 3. Fallback Count (`llm_gateway_fallbacks_total`)

**Type**: Counter  
**Labels**: `api_key_id`, `from_provider`, `to_provider`

**Example**:
```
llm_gateway_fallbacks_total{api_key_id="123",from_provider="openai",to_provider="deepseek"} 10
```

**Usage in Prometheus**:
```promql
# Total fallbacks
sum(llm_gateway_fallbacks_total)

# Fallback rate
rate(llm_gateway_fallbacks_total[5m])

# Fallbacks by provider pair
sum by (from_provider, to_provider) (llm_gateway_fallbacks_total)
```

#### 4. Cost Total (`llm_gateway_cost_total`)

**Type**: Counter  
**Labels**: `api_key_id`, `provider`, `model`

**Example**:
```
llm_gateway_cost_total{api_key_id="123",provider="openai",model="gpt-3.5-turbo"} 12.45
```

**Usage in Prometheus**:
```promql
# Total cost
sum(llm_gateway_cost_total)

# Cost per provider
sum by (provider) (llm_gateway_cost_total)

# Cost rate per hour
rate(llm_gateway_cost_total[1h]) * 3600
```

#### 5. Latency (`llm_gateway_latency_seconds`)

**Type**: Histogram  
**Labels**: `api_key_id`, `provider`  
**Buckets**: `0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0`

**Example**:
```
llm_gateway_latency_seconds_bucket{api_key_id="123",provider="openai",le="1.0"} 1200
llm_gateway_latency_seconds_bucket{api_key_id="123",provider="openai",le="2.0"} 1450
llm_gateway_latency_seconds_sum{api_key_id="123",provider="openai"} 1800.5
llm_gateway_latency_seconds_count{api_key_id="123",provider="openai"} 1500
```

**Usage in Prometheus**:
```promql
# P50 latency (median)
histogram_quantile(0.50, rate(llm_gateway_latency_seconds_bucket[5m]))

# P95 latency
histogram_quantile(0.95, rate(llm_gateway_latency_seconds_bucket[5m]))

# P99 latency
histogram_quantile(0.99, rate(llm_gateway_latency_seconds_bucket[5m]))

# Average latency
rate(llm_gateway_latency_seconds_sum[5m]) / rate(llm_gateway_latency_seconds_count[5m])

# Latency by provider
histogram_quantile(0.95, sum by (provider, le) (rate(llm_gateway_latency_seconds_bucket[5m])))
```

### Structured Logging

All logs are structured in JSON format with the following fields:

**Standard Fields**:
- `timestamp`: ISO format timestamp
- `level`: Log level (INFO, ERROR, WARNING)
- `message`: Log message
- `module`: Python module name
- `function`: Function name
- `line`: Line number

**Request-Specific Fields**:
- `request_id`: Unique request identifier (format: `req-{hex}`)
- `api_key_id`: API key UUID
- `provider`: Provider used
- `latency_ms`: Request latency in milliseconds
- `cost_usd`: Request cost in USD
- `fallback_used`: Boolean indicating if fallback occurred

**Example Log Entry**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "message": "Request completed",
  "module": "routes",
  "function": "chat_completions",
  "line": 197,
  "request_id": "req-abc123def456",
  "api_key_id": "123e4567-e89b-12d3-a456-426614174000",
  "provider": "openai",
  "latency_ms": 1200,
  "cost_usd": 0.00025,
  "fallback_used": false
}
```

### Viewing Logs

**Via Docker**:
```bash
# All logs
docker-compose logs app

# Follow logs in real-time
docker-compose logs -f app

# Filter by request_id
docker-compose logs app | grep "req-abc123"

# Filter errors only
docker-compose logs app | jq 'select(.level == "ERROR")'
```

**Searching Logs**:
```bash
# Find all requests for a specific API key
docker-compose logs app | jq 'select(.api_key_id == "123e4567-...")'

# Find all fallbacks
docker-compose logs app | jq 'select(.fallback_used == true)'

# Find expensive requests (cost > $0.01)
docker-compose logs app | jq 'select(.cost_usd > 0.01)'
```

### Request ID Traceability

Every request gets a unique `request_id` that is:
1. Generated at the start of the request
2. Included in all logs related to that request
3. Stored in the database (cost_records, request_logs)
4. Returned in error messages (if applicable)

**Tracing a Request**:
```bash
# 1. Get request_id from error message or response
request_id="req-abc123def456"

# 2. Search logs for that request_id
docker-compose logs app | grep "$request_id"

# 3. Query database for that request
# (via cost analytics API)
curl -X GET "http://localhost:8000/v1/costs/records?limit=1000" \
  -H "Authorization: Bearer YOUR_API_KEY" | jq ".[] | select(.request_id == \"$request_id\")"
```

---

## How to Use Each Feature

### Setting Up Cost Tracking

Cost tracking is **automatic** - no setup required! Just make requests and costs are tracked.

**Verify it's working**:
```bash
# Make a request
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"messages": [{"role": "user", "content": "Test"}]}'

# Check if cost was recorded
curl -X GET "http://localhost:8000/v1/costs/records?limit=1" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Configuring Failure Handling

**Timeouts**:
```bash
# In .env file
PROVIDER_TIMEOUT=30  # seconds (default: 30)
```

**Fallback Chain**: Configured in `app/routing/rules.py`:
```python
def get_provider_fallback_chain():
    return [
        OpenAIProvider(),      # Primary
        DeepSeekProvider(),    # Secondary
        HuggingFaceProvider(), # Tertiary
    ]
```

### Setting Up Metrics Collection

**1. Configure Prometheus** (prometheus.yml):
```yaml
scrape_configs:
  - job_name: 'llm-gateway'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

**2. Access Metrics**:
```bash
curl http://localhost:8000/metrics
```

**3. Query in Prometheus**:
```
# Success rate
sum(rate(llm_gateway_requests_total{status="success"}[5m])) / sum(rate(llm_gateway_requests_total[5m]))

# P95 latency
histogram_quantile(0.95, rate(llm_gateway_latency_seconds_bucket[5m]))

# Error rate
rate(llm_gateway_errors_total[5m])

# Total cost
sum(llm_gateway_cost_total)
```

### Configuring Logging

**Log Level** (in .env):
```bash
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR
```

**Log Format**: JSON (automatic, no configuration needed)

**Log Output**: stdout (captured by Docker logs)

---

## Best Practices

### Cost Tracking

1. **Monitor Regularly**: Check `/v1/costs` endpoint regularly
2. **Set Budget Alerts**: Use Prometheus alerts based on `llm_gateway_cost_total`
3. **Analyze Trends**: Use date range filters to analyze cost trends
4. **Optimize Provider Selection**: Use cost analytics to choose optimal providers

### Failure Handling

1. **Monitor Fallbacks**: Track `llm_gateway_fallbacks_total` to identify provider issues
2. **Adjust Timeouts**: If timeouts are frequent, consider increasing `PROVIDER_TIMEOUT`
3. **Monitor Errors**: Track `llm_gateway_errors_total` by error_type
4. **Test Fallback Chain**: Periodically test that fallback works correctly

### Observability

1. **Set Up Prometheus**: Configure Prometheus to scrape metrics endpoint
2. **Create Dashboards**: Build Grafana dashboards for visualization
3. **Set Alerts**: Configure alerts for high error rates, latency, or costs
4. **Centralized Logging**: Consider sending logs to centralized logging system (ELK, Loki, etc.)
5. **Request Tracing**: Use request_id to trace requests through the system

---

## Troubleshooting

### Costs Not Being Recorded

**Check**:
1. Database connection: `docker-compose logs app | grep database`
2. API key is valid
3. Request succeeded (check response status)

**Fix**:
```bash
# Verify database connection
python scripts/init_db.py

# Check if cost records table exists
# (via database client or Supabase dashboard)
```

### Metrics Not Showing

**Check**:
1. Metrics endpoint is accessible: `curl http://localhost:8000/metrics`
2. Requests are being made (metrics only update on requests)
3. Prometheus is configured to scrape the endpoint

**Fix**:
```bash
# Test metrics endpoint directly
curl http://localhost:8000/metrics

# Make a test request to generate metrics
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"messages": [{"role": "user", "content": "test"}]}'
```

### Logs Not Structured

**Check**:
1. Logging is initialized: Check `app/main.py` calls `setup_logging()`
2. Log level is set correctly in `.env`

**Fix**:
```bash
# Ensure LOG_LEVEL is set in .env
echo "LOG_LEVEL=INFO" >> .env

# Restart application
docker-compose restart app
```

---

## Summary

All PRD requirements are fully implemented and ready to use:

- ✅ **Cost Attribution**: Automatic, no setup needed
- ✅ **Failure Handling**: Automatic fallback, configurable timeouts
- ✅ **Observability**: Metrics endpoint and structured logging

Everything works out of the box - just start making requests!

