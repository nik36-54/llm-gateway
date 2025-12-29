# LLM Cost & Reliability Governance Gateway

A production-grade backend service that sits between applications and LLM providers to enforce governance, observability, and deterministic behavior. This gateway provides cost tracking, rate limiting, provider routing, and comprehensive observability for LLM usage.

## Features

- **API Key Authentication**: Secure API key-based authentication with per-key usage tracking
- **Rate Limiting**: Token bucket rate limiting per API key
- **Deterministic Routing**: Intelligent provider selection based on task type, budget, and latency requirements
- **Vendor Abstraction**: Unified interface supporting OpenAI, DeepSeek, and HuggingFace (Llama-3, Mixtral, Qwen)
- **Cost Attribution**: Per-request cost tracking and aggregation by API key, provider, and model
- **Fallback Handling**: Automatic fallback to secondary providers on failures
- **Observability**: Prometheus metrics and structured JSON logging
- **Production Ready**: Docker deployment, health checks, and comprehensive error handling

## Architecture

```
Client Application
    ↓
FastAPI Gateway (Authentication, Rate Limiting, Routing)
    ↓
Provider Adapters (OpenAI, DeepSeek, HuggingFace)
    ↓
LLM Providers (GPT-3.5/4, DeepSeek Chat, Llama-3/Mixtral/Qwen)
    ↓
Cost Tracking → Supabase PostgreSQL
    ↓
Metrics → Prometheus
```

## Quick Start

> **For detailed setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)**

## Quick Start (Summary)

### Prerequisites

- Docker and Docker Compose (optional, for local DB)
- Python 3.11+ (for local development)
- Supabase account (for PostgreSQL database)
- API keys: OpenAI, DeepSeek, HuggingFace

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# Provider API Keys
OPENAI_API_KEY=sk-your-openai-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here
HUGGINGFACE_API_KEY=hf_your-huggingface-api-key-here

# Security
SECRET_KEY=change-me-in-production-use-a-random-string

# Logging
LOG_LEVEL=INFO
ENVIRONMENT=dev

# Provider timeout (seconds)
PROVIDER_TIMEOUT=30
```

### Docker Deployment

1. **Start services**:
   ```bash
   docker-compose up -d
   ```

2. **Run database migrations** (first time only):
   ```bash
   docker-compose exec app alembic upgrade head
   ```

3. **Create an API key** (using Python shell or script):
   ```python
   from app.cost.database import SessionLocal
   from app.cost.models import APIKey
   from app.auth.api_key import hash_api_key
   import uuid

   db = SessionLocal()
   api_key_record = APIKey(
       id=uuid.uuid4(),
       key_hash=hash_api_key("your-plain-api-key-here"),
       name="Test Key",
       rate_limit_per_minute=60,
       is_active=True
   )
   db.add(api_key_record)
   db.commit()
   ```

4. **Access the service**:
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Metrics: http://localhost:8000/metrics
   - Health: http://localhost:8000/health

## API Documentation

### Chat Completions

**Endpoint**: `POST /v1/chat/completions`

**Headers**:
```
Authorization: Bearer <your-api-key>
Content-Type: application/json
```

**Request Body**:
```json
{
  "task": "summarization",
  "budget": "low",
  "latency_sensitive": false,
  "messages": [
    {
      "role": "user",
      "content": "Summarize this text: ..."
    }
  ],
  "model": "gpt-3.5-turbo",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Parameters**:
- `task` (optional): Task type - `"summarization"`, `"reasoning"`, or `"general"`
- `budget` (optional): Budget level - `"low"`, `"medium"`, or `"high"`
- `latency_sensitive` (optional): Boolean indicating if latency is a priority
- `messages` (required): Array of message objects with `role` and `content`
- `model` (optional): Model override (defaults to provider's default)
- `temperature` (optional): Sampling temperature (0-2, default: 0.7)
- `max_tokens` (optional): Maximum tokens to generate

**Response**:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-3.5-turbo",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Summary: ..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  },
  "provider": "openai",
  "cost_usd": 0.00025
}
```

### Metrics

**Endpoint**: `GET /metrics`

Returns Prometheus-formatted metrics including:
- `llm_gateway_requests_total`: Total request count
- `llm_gateway_errors_total`: Error count by type
- `llm_gateway_fallbacks_total`: Fallback count
- `llm_gateway_cost_total`: Total cost in USD
- `llm_gateway_latency_seconds`: Request latency histogram

### Health Check

**Endpoint**: `GET /health`

Returns service health status.

### Cost Analytics

**Endpoint**: `GET /v1/costs`

Get cost summary and aggregates by provider, model, and API key.

**Query Parameters**:
- `start_date` (optional): Start date filter (ISO format)
- `end_date` (optional): End date filter (ISO format)
- `provider` (optional): Filter by provider name
- `model` (optional): Filter by model name

**Response**:
```json
{
  "total_cost_usd": 0.12345,
  "total_requests": 100,
  "total_tokens_in": 50000,
  "total_tokens_out": 25000,
  "total_tokens": 75000,
  "by_provider": [
    {
      "provider": "openai",
      "total_cost_usd": 0.10000,
      "request_count": 80,
      "total_tokens_in": 40000,
      "total_tokens_out": 20000,
      "total_tokens": 60000,
      "avg_latency_ms": 1200.5
    }
  ],
  "by_model": [...],
  "by_api_key": [...],
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-31T23:59:59Z"
  }
}
```

**Endpoint**: `GET /v1/costs/records`

Get detailed cost records with pagination.

**Query Parameters**:
- `start_date` (optional): Start date filter (ISO format)
- `end_date` (optional): End date filter (ISO format)
- `provider` (optional): Filter by provider name
- `model` (optional): Filter by model name
- `limit` (optional): Maximum records to return (1-1000, default: 100)
- `offset` (optional): Number of records to skip (default: 0)

**Response**: Array of cost record objects with detailed information.

### Overview/Dashboard Stats

**Endpoint**: `GET /v1/overview`

Get overview statistics for dashboard display. Requires authentication.

**Headers**:
```
Authorization: Bearer <your-api-key>
```

**Response**:
```json
{
  "total_routed_requests": 1200,
  "aggregated_savings_usd": 42.5,
  "integrated_providers": 3,
  "current_cost_usd": 15.75,
  "savings_percentage": 72.9,
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "description": "Reliable general performance",
      "models": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
      "pricing_note": "$0.0015/1K input, $0.002/1K output (GPT-3.5)",
      "speed_rating": "fastest",
      "cost_rating": "moderate",
      "icon_color": "#10a37f"
    },
    {
      "name": "deepseek",
      "display_name": "DeepSeek",
      "description": "Cost-effective operations",
      "models": ["deepseek-chat", "deepseek-coder"],
      "pricing_note": "$0.00014/1K input, $0.00028/1K output",
      "speed_rating": "fast",
      "cost_rating": "cheapest",
      "icon_color": "#f59e0b"
    },
    {
      "name": "huggingface",
      "display_name": "HuggingFace",
      "description": "Open-source models",
      "models": ["llama-3", "mixtral", "qwen"],
      "pricing_note": "Free (via Inference API)",
      "speed_rating": "moderate",
      "cost_rating": "free",
      "icon_color": "#8b5cf6"
    }
  ]
}
```

**Fields**:
- `total_routed_requests`: Total number of requests processed (all time)
- `aggregated_savings_usd`: Total savings compared to using only OpenAI GPT-3.5-turbo
- `integrated_providers`: Number of available providers (always 3)
- `current_cost_usd`: Actual cost spent so far
- `savings_percentage`: Percentage savings compared to baseline
- `providers`: Array of provider information for UI display

### Routing Preview

**Endpoint**: `GET /v1/routing/preview`

Preview which provider would be selected based on routing settings. Does NOT require authentication.

**Query Parameters**:
- `task` (optional): Task type - `"summarization"`, `"reasoning"`, or `"general"`
- `budget` (optional): Budget level - `"low"`, `"medium"`, or `"high"`
- `latency_sensitive` (optional): Boolean indicating if latency is a priority (default: false)

**Response**:
```json
{
  "selected_provider": "deepseek",
  "provider_name": "DeepSeek",
  "reason": "Selected because: Task = Summarization, Budget = Low",
  "fallback_chain": ["openai", "huggingface", "deepseek"]
}
```

**Fields**:
- `selected_provider`: Provider ID that would be selected
- `provider_name`: Human-readable provider name
- `reason`: Explanation of why this provider was selected
- `fallback_chain`: List of providers in fallback order

**Example**:
```bash
curl "http://localhost:8000/v1/routing/preview?task=summarization&budget=low"
```

### Provider Information

**Endpoint**: `GET /v1/providers`

Get list of all available providers with their information. Does NOT require authentication.

**Response**: Array of provider information objects (same structure as in `/v1/overview` response).

**Example**:
```bash
curl http://localhost:8000/v1/providers
```

### Analytics Dashboard

**Endpoint**: `GET /v1/analytics`

Get analytics dashboard data with KPIs, trends, and chart data. Requires authentication.

**Headers**:
```
Authorization: Bearer <your-api-key>
```

**Query Parameters**:
- `period` (optional): Time period for analytics - `"1D"`, `"7D"`, `"30D"`, or `"ALL"` (default: `"7D"`)

**Response**:
```json
{
  "total_cost": {
    "value": 142.50,
    "label": "TOTAL COST",
    "trend_percentage": 12.5,
    "trend_direction": "up"
  },
  "total_requests": {
    "value": 12450,
    "label": "TOTAL REQUESTS",
    "trend_percentage": 5.2,
    "trend_direction": "up"
  },
  "average_latency": {
    "value": 840.0,
    "label": "AVG. LATENCY",
    "trend_percentage": 15.4,
    "trend_direction": "down"
  },
  "tokens_used": {
    "value": 15400000,
    "label": "TOKENS USED",
    "trend_percentage": 8.1,
    "trend_direction": "up"
  },
  "cost_trend": [
    {
      "date": "2024-01-15",
      "day_name": "Mon",
      "cost_usd": 12.50
    },
    {
      "date": "2024-01-16",
      "day_name": "Tue",
      "cost_usd": 15.20
    }
  ],
  "cost_by_provider": [
    {
      "provider": "openai",
      "cost_usd": 85.20,
      "percentage": 59.8,
      "color": "#10a37f"
    },
    {
      "provider": "deepseek",
      "cost_usd": 42.30,
      "percentage": 29.7,
      "color": "#f59e0b"
    },
    {
      "provider": "huggingface",
      "cost_usd": 15.00,
      "percentage": 10.5,
      "color": "#8b5cf6"
    }
  ],
  "period": "7D",
  "start_date": "2024-01-08T00:00:00Z",
  "end_date": "2024-01-15T23:59:59Z"
}
```

**Fields**:
- `total_cost`, `total_requests`, `average_latency`, `tokens_used`: KPI metrics with values and trend percentages
- `cost_trend`: Array of daily cost data points for line chart (daily for 1D/7D/30D, monthly for ALL)
- `cost_by_provider`: Provider breakdown with costs and percentages for donut chart
- `period`: Selected time period
- `start_date`, `end_date`: Date range for the analytics

**Example**:
```bash
curl -X GET "http://localhost:8000/v1/analytics?period=7D" \
  -H "Authorization: Bearer your-api-key"
```

### Recent Transactions

**Endpoint**: `GET /v1/transactions/recent`

Get recent API transactions for the transactions table. Requires authentication.

**Headers**:
```
Authorization: Bearer <your-api-key>
```

**Query Parameters**:
- `limit` (optional): Number of recent transactions to return (1-100, default: 10)

**Response**:
```json
{
  "transactions": [
    {
      "id": "uuid",
      "timestamp": "2024-12-24T23:56:00Z",
      "provider": "openai",
      "model": "gpt-4o",
      "tokens": 1650,
      "cost_usd": 0.01500,
      "latency_ms": 2400
    },
    {
      "id": "uuid",
      "timestamp": "2024-12-24T22:56:00Z",
      "provider": "deepseek",
      "model": "deepseek-chat",
      "tokens": 970,
      "cost_usd": 0.00020,
      "latency_ms": 1100
    },
    {
      "id": "uuid",
      "timestamp": "2024-12-24T21:56:00Z",
      "provider": "huggingface",
      "model": "llama-3",
      "tokens": 750,
      "cost_usd": 0.00000,
      "latency_ms": 4500
    }
  ],
  "total": 12450
}
```

**Fields**:
- `transactions`: Array of recent transaction records ordered by timestamp (most recent first)
- `total`: Total number of transactions in the database (for pagination)

**Example**:
```bash
curl -X GET "http://localhost:8000/v1/transactions/recent?limit=20" \
  -H "Authorization: Bearer your-api-key"
```

**Cost Records Endpoint** (from earlier):
- `end_date` (optional): End date filter (ISO format)
- `provider` (optional): Filter by provider name
- `model` (optional): Filter by model name
- `limit` (optional): Maximum records to return (1-1000, default: 100)
- `offset` (optional): Number of records to skip (default: 0)

**Response**:
```json
[
  {
    "id": "uuid",
    "request_id": "req-123456",
    "provider": "openai",
    "model": "gpt-3.5-turbo",
    "tokens_in": 100,
    "tokens_out": 50,
    "total_tokens": 150,
    "cost_usd": 0.00025,
    "latency_ms": 1200,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

## Routing Rules

The gateway uses deterministic routing rules to select the appropriate LLM provider:

1. **Task-based routing**:
   - `task="summarization"` → DeepSeek (low cost)
   - `task="reasoning"` → HuggingFace (open-source models)

2. **Latency-sensitive routing**:
   - `latency_sensitive=true` → OpenAI (fastest)

3. **Budget-based routing**:
   - `budget="low"` → DeepSeek
   - `budget="high"` → OpenAI

4. **Default**: OpenAI

Priority order: Task → Latency → Budget → Default

## Cost Tracking

The gateway tracks costs for every request:

- **Storage**: Cost records stored in PostgreSQL `cost_records` table
- **Aggregation**: Costs can be aggregated by:
  - API key
  - Provider
  - Model
  - Date range

**Pricing Tables** (per 1K tokens):
- OpenAI GPT-4: $0.03 input / $0.06 output
- OpenAI GPT-3.5: $0.0015 input / $0.002 output
- DeepSeek Chat: $0.00014 input / $0.00028 output
- HuggingFace (Llama-3/Mixtral/Qwen): Free (via Inference API)

## Example Requests

### Basic Request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

### Summarization Task

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "summarization",
    "budget": "low",
    "messages": [
      {"role": "user", "content": "Summarize this long text..."}
    ]
  }'
```

### Latency-Sensitive Request

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "latency_sensitive": true,
    "messages": [
      {"role": "user", "content": "Quick response needed"}
    ]
  }'
```

### Get Cost Summary

```bash
# Get cost summary for your API key
curl -X GET "http://localhost:8000/v1/costs" \
  -H "Authorization: Bearer your-api-key"

# Get cost summary filtered by date range and provider
curl -X GET "http://localhost:8000/v1/costs?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z&provider=openai" \
  -H "Authorization: Bearer your-api-key"
```

### Get Cost Records

```bash
# Get detailed cost records (last 100)
curl -X GET "http://localhost:8000/v1/costs/records?limit=100" \
  -H "Authorization: Bearer your-api-key"

# Get cost records for specific provider
curl -X GET "http://localhost:8000/v1/costs/records?provider=deepseek&limit=50" \
  -H "Authorization: Bearer your-api-key"
```

## Development

### Local Development Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL**:
   ```bash
   docker-compose up -d db
   ```

3. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Run the application**:
   ```bash
   uvicorn app.main:app --reload
   ```

### Running Tests

```bash
pytest
```

### Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

## Deployment

### Production Considerations

1. **Environment Variables**: Use secure secret management for API keys and secrets
2. **Database**: Use managed PostgreSQL service (AWS RDS, Google Cloud SQL, etc.)
3. **Scaling**: Rate limiting is in-memory - consider Redis for multi-instance deployments
4. **Security**: 
   - Use HTTPS in production
   - Restrict CORS origins
   - Rotate SECRET_KEY regularly
   - Use strong API key hashing (bcrypt already configured)

### Deployment Platforms

- **Google Cloud Run**: Serverless container deployment (recommended - see SETUP_GUIDE.md)
- **Railway**: Deploy via GitHub
- **Render**: Deploy with managed PostgreSQL
- **AWS ECS/Fargate**: Container-based deployment

**See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete deployment instructions.**

## Project Structure

```
llm-production/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── api/
│   │   └── routes.py        # API endpoints
│   ├── auth/
│   │   ├── api_key.py       # API key authentication
│   │   └── rate_limiter.py  # Rate limiting
│   ├── routing/
│   │   ├── router.py        # Provider selection logic
│   │   └── rules.py         # Routing rules
│   ├── providers/
│   │   ├── base.py          # Provider interface
│   │   ├── openai.py        # OpenAI adapter
│   │   ├── huggingface.py   # HuggingFace adapter
│   │   └── deepseek.py      # DeepSeek adapter
│   ├── cost/
│   │   ├── models.py        # Database models
│   │   ├── database.py      # Database connection
│   │   └── tracker.py       # Cost tracking
│   ├── metrics/
│   │   └── prometheus.py    # Metrics collection
│   └── utils/
│       ├── retry.py         # Retry and fallback logic
│       └── logging.py       # Structured logging
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── docker-compose.yml       # Local development setup
├── Dockerfile              # Application container
└── requirements.txt        # Python dependencies
```

## License

MIT

## Implementation Verification

**All PRD requirements are fully implemented and verified.** See:
- [PRD_IMPLEMENTATION_STATUS.md](PRD_IMPLEMENTATION_STATUS.md) - Complete verification report
- [IMPLEMENTATION_VERIFICATION.md](IMPLEMENTATION_VERIFICATION.md) - Detailed implementation checks
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - How to use all features

### Verified Features

✅ **Cost Attribution** - All data fields collected, persisted, and aggregated  
✅ **Production Failure Handling** - Timeouts, retries, fallbacks all implemented  
✅ **Observability & Metrics** - Prometheus metrics and structured logging fully operational

## Contributing

This is a demonstration project showcasing production-grade backend engineering practices. Contributions and feedback are welcome!

