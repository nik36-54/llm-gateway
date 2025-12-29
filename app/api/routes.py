import uuid
import time
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, cast, Date, extract
from prometheus_client import generate_latest
from fastapi.responses import Response
from decimal import Decimal

from app.cost.models import APIKey, RequestLog, CostRecord
from app.cost.database import get_db
from app.auth.api_key import get_api_key
from app.auth.rate_limiter import rate_limiter
from app.routing.router import select_provider
from app.routing.rules import get_provider_fallback_chain
from app.utils.retry import call_with_fallback
from app.cost.tracker import record_cost
from app.providers.base import ProviderError
from app.metrics.prometheus import (
    record_request,
    record_error,
    record_fallback,
    record_cost as record_cost_metric,
    record_latency,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Data Contracts for the API endpoints to use when sending and receiving data between the client and the server using Pydantic BaseModels.
class Message(BaseModel):
    """Chat message model."""

    role: str = Field(..., description="Role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""

    task: Optional[str] = Field(
        None, description="Task type: summarization, reasoning, general"
    )
    budget: Optional[str] = Field(None, description="Budget level: low, medium, high")
    latency_sensitive: bool = Field(
        False, description="Whether latency is a priority"
    )
    messages: List[Message] = Field(..., description="Chat messages")
    model: Optional[str] = Field(None, description="Model override (optional)")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens to generate")


class Choice(BaseModel):
    """Choice in chat completion response."""

    index: int
    message: Message
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat completion response model."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage
    provider: str
    cost_usd: float


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db),
):
    """
    Chat completion endpoint with routing, cost tracking, and fallback handling.
    """
    request_id = f"req-{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    provider_used = None
    fallback_used = False
    status_str = "success"

    try:
        # Rate limiting check
        rate_limiter.check_rate_limit(api_key)

        # Select primary provider
        # Note: model parameter is for provider model selection, not provider override
        primary_provider = select_provider(
            task=request.task,
            budget=request.budget,
            latency_sensitive=request.latency_sensitive,
            provider_override=None,  # No provider override from request
        )

        # Get fallback chain (primary + fallbacks)
        fallback_chain = get_provider_fallback_chain()
        # Ensure primary provider is first
        providers_to_try = [primary_provider] + [
            p for p in fallback_chain if p.name != primary_provider.name
        ][:2]  # Limit to 3 providers total

        # Convert messages to dict format
        messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        # Call provider with fallback
        try:
            provider_response, provider_used, fallback_used = await call_with_fallback(
                providers=providers_to_try,
                messages=messages_dict,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except ProviderError as e:
            status_str = "failure"
            record_error(str(api_key.id), provider_used or "unknown", type(e).__name__)
            logger.error(
                f"Provider error",
                extra={
                    "request_id": request_id,
                    "api_key_id": str(api_key.id),
                    "provider": provider_used or "unknown",
                    "error": str(e),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM provider error: {str(e)}",
            )

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        latency_seconds = (time.time() - start_time)

        # Record cost to database
        try:
            cost_record = record_cost(
                db=db,
                api_key=api_key,
                provider_response=provider_response,
                request_id=request_id,
                latency_ms=latency_ms,
            )
            cost_usd = float(cost_record.cost_usd)
        except Exception as e:
            logger.error(f"Failed to record cost: {e}", extra={"request_id": request_id})
            cost_usd = 0.0

        # Record request log
        try:
            request_log = RequestLog(
                request_id=request_id,
                api_key_id=api_key.id,
                task=request.task,
                budget=request.budget,
                latency_sensitive=request.latency_sensitive,
                provider_used=provider_used,
                status=status_str,
            )
            db.add(request_log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record request log: {e}", extra={"request_id": request_id})
            db.rollback()

        # Record metrics
        record_request(str(api_key.id), provider_used, status_str)
        record_cost_metric(str(api_key.id), provider_used, provider_response.model, cost_usd)
        record_latency(str(api_key.id), provider_used, latency_seconds)

        if fallback_used:
            record_fallback(str(api_key.id), primary_provider.name, provider_used)

        # Structured logging
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "api_key_id": str(api_key.id),
                "provider": provider_used,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                "fallback_used": fallback_used,
            },
        )

        # Build response
        return ChatCompletionResponse(
            id=provider_response.request_id,
            created=int(time.time()),
            model=provider_response.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=provider_response.content),
                    finish_reason=provider_response.finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=provider_response.tokens_in,
                completion_tokens=provider_response.tokens_out,
                total_tokens=provider_response.tokens_in + provider_response.tokens_out,
            ),
            provider=provider_used,
            cost_usd=cost_usd,
        )

    except HTTPException:
        raise
    except Exception as e:
        status_str = "failure"
        record_error(str(api_key.id), provider_used or "unknown", type(e).__name__)
        logger.error(
            f"Unexpected error",
            extra={
                "request_id": request_id,
                "api_key_id": str(api_key.id),
                "error": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "llm-gateway"}


# Cost Analytics Models
class CostRecordDetail(BaseModel):
    """Detailed cost record response."""

    id: str
    request_id: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    created_at: datetime

    class Config:
        from_attributes = True


class CostAggregate(BaseModel):
    """Cost aggregation response."""

    provider: Optional[str] = None
    model: Optional[str] = None
    api_key_name: Optional[str] = None
    total_cost_usd: float
    request_count: int
    total_tokens_in: int
    total_tokens_out: int
    total_tokens: int
    avg_latency_ms: float


class CostSummaryResponse(BaseModel):
    """Cost summary response."""

    total_cost_usd: float
    total_requests: int
    total_tokens_in: int
    total_tokens_out: int
    total_tokens: int
    by_provider: List[CostAggregate]
    by_model: List[CostAggregate]
    by_api_key: List[CostAggregate]
    time_range: Dict[str, Optional[datetime]]


@router.get("/v1/costs", response_model=CostSummaryResponse)
async def get_cost_summary(
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    model: Optional[str] = Query(None, description="Filter by model"),
):
    """
    Get cost summary and aggregates.

    Returns aggregated cost data by provider, model, and API key.
    Supports filtering by date range, provider, and model.
    """
    try:
        # Build base query - filter by API key and optional filters
        query = db.query(CostRecord).filter(CostRecord.api_key_id == api_key.id)

        # Apply date filters
        if start_date:
            query = query.filter(CostRecord.created_at >= start_date)
        if end_date:
            query = query.filter(CostRecord.created_at <= end_date)

        # Apply provider/model filters
        if provider:
            query = query.filter(CostRecord.provider == provider)
        if model:
            query = query.filter(CostRecord.model == model)

        # Get total summary
        total_summary = query.with_entities(
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.count(CostRecord.id).label("total_requests"),
            func.sum(CostRecord.tokens_in).label("total_tokens_in"),
            func.sum(CostRecord.tokens_out).label("total_tokens_out"),
        ).first()

        total_cost = float(total_summary.total_cost or 0)
        total_requests = total_summary.total_requests or 0
        total_tokens_in = total_summary.total_tokens_in or 0
        total_tokens_out = total_summary.total_tokens_out or 0

        # Aggregate by provider
        provider_query = query.with_entities(
            CostRecord.provider,
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.count(CostRecord.id).label("request_count"),
            func.sum(CostRecord.tokens_in).label("total_tokens_in"),
            func.sum(CostRecord.tokens_out).label("total_tokens_out"),
            func.avg(CostRecord.latency_ms).label("avg_latency"),
        ).group_by(CostRecord.provider)

        by_provider = [
            CostAggregate(
                provider=row.provider,
                total_cost_usd=float(row.total_cost or 0),
                request_count=row.request_count or 0,
                total_tokens_in=row.total_tokens_in or 0,
                total_tokens_out=row.total_tokens_out or 0,
                total_tokens=(row.total_tokens_in or 0) + (row.total_tokens_out or 0),
                avg_latency_ms=float(row.avg_latency or 0),
            )
            for row in provider_query.all()
        ]

        # Aggregate by model
        model_query = query.with_entities(
            CostRecord.model,
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.count(CostRecord.id).label("request_count"),
            func.sum(CostRecord.tokens_in).label("total_tokens_in"),
            func.sum(CostRecord.tokens_out).label("total_tokens_out"),
            func.avg(CostRecord.latency_ms).label("avg_latency"),
        ).group_by(CostRecord.model)

        by_model = [
            CostAggregate(
                model=row.model,
                total_cost_usd=float(row.total_cost or 0),
                request_count=row.request_count or 0,
                total_tokens_in=row.total_tokens_in or 0,
                total_tokens_out=row.total_tokens_out or 0,
                total_tokens=(row.total_tokens_in or 0) + (row.total_tokens_out or 0),
                avg_latency_ms=float(row.avg_latency or 0),
            )
            for row in model_query.all()
        ]

        # Aggregate by API key (for this key)
        key_query = query.join(APIKey, CostRecord.api_key_id == APIKey.id).with_entities(
            APIKey.name,
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.count(CostRecord.id).label("request_count"),
            func.sum(CostRecord.tokens_in).label("total_tokens_in"),
            func.sum(CostRecord.tokens_out).label("total_tokens_out"),
            func.avg(CostRecord.latency_ms).label("avg_latency"),
        ).group_by(APIKey.name)

        by_api_key = [
            CostAggregate(
                api_key_name=row.name,
                total_cost_usd=float(row.total_cost or 0),
                request_count=row.request_count or 0,
                total_tokens_in=row.total_tokens_in or 0,
                total_tokens_out=row.total_tokens_out or 0,
                total_tokens=(row.total_tokens_in or 0) + (row.total_tokens_out or 0),
                avg_latency_ms=float(row.avg_latency or 0),
            )
            for row in key_query.all()
        ]

        return CostSummaryResponse(
            total_cost_usd=total_cost,
            total_requests=total_requests,
            total_tokens_in=total_tokens_in,
            total_tokens_out=total_tokens_out,
            total_tokens=total_tokens_in + total_tokens_out,
            by_provider=by_provider,
            by_model=by_model,
            by_api_key=by_api_key,
            time_range={"start": start_date, "end": end_date},
        )

    except Exception as e:
        logger.error(f"Error fetching cost summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cost summary: {str(e)}",
        )


@router.get("/v1/costs/records", response_model=List[CostRecordDetail])
async def get_cost_records(
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    model: Optional[str] = Query(None, description="Filter by model"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
):
    """
    Get detailed cost records.

    Returns paginated list of cost records with filtering options.
    """
    try:
        # Build base query
        query = db.query(CostRecord).filter(CostRecord.api_key_id == api_key.id)

        # Apply filters
        if start_date:
            query = query.filter(CostRecord.created_at >= start_date)
        if end_date:
            query = query.filter(CostRecord.created_at <= end_date)
        if provider:
            query = query.filter(CostRecord.provider == provider)
        if model:
            query = query.filter(CostRecord.model == model)

        # Order by most recent first and paginate
        records = (
            query.order_by(CostRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            CostRecordDetail(
                id=str(record.id),
                request_id=record.request_id,
                provider=record.provider,
                model=record.model,
                tokens_in=record.tokens_in,
                tokens_out=record.tokens_out,
                total_tokens=record.tokens_in + record.tokens_out,
                cost_usd=float(record.cost_usd),
                latency_ms=record.latency_ms,
                created_at=record.created_at,
            )
            for record in records
        ]

    except Exception as e:
        logger.error(f"Error fetching cost records: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching cost records: {str(e)}",
        )


# Overview/Dashboard Models
class ProviderInfo(BaseModel):
    """Provider information for frontend display."""

    name: str
    display_name: str
    description: str
    models: List[str]
    pricing_note: str
    speed_rating: str  # "fastest", "fast", "moderate"
    cost_rating: str  # "expensive", "moderate", "cheapest", "free"
    icon_color: str  # Color code for UI


class RoutingPreviewResponse(BaseModel):
    """Routing preview response showing which provider will be selected."""

    selected_provider: str
    provider_name: str
    reason: str
    fallback_chain: List[str]


class OverviewStatsResponse(BaseModel):
    """Overview/dashboard statistics."""

    total_routed_requests: int
    aggregated_savings_usd: float
    integrated_providers: int
    current_cost_usd: float
    savings_percentage: float
    providers: List[ProviderInfo]


@router.get("/v1/overview", response_model=OverviewStatsResponse)
async def get_overview_stats(
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db),
):
    """
    Get overview statistics for dashboard.

    Returns:
    - Total routed requests (all time)
    - Aggregated savings (compared to using only OpenAI)
    - Number of integrated providers
    - Current total cost
    - Savings percentage
    - Provider information
    """
    try:
        # Get total requests for this API key
        total_requests = db.query(func.count(CostRecord.id)).filter(
            CostRecord.api_key_id == api_key.id
        ).scalar() or 0

        # Get all cost records for this API key
        all_records = db.query(CostRecord).filter(
            CostRecord.api_key_id == api_key.id
        ).all()

        # Calculate actual cost spent
        actual_cost = sum(float(record.cost_usd) for record in all_records)

        # Calculate what it would have cost if all requests used OpenAI GPT-3.5-turbo
        # (most common baseline)
        openai_gpt35_input_price = Decimal("0.0015")
        openai_gpt35_output_price = Decimal("0.002")

        baseline_cost = Decimal("0")
        for record in all_records:
            # Calculate cost if this request used OpenAI GPT-3.5-turbo
            input_cost = (Decimal(record.tokens_in) / Decimal("1000")) * openai_gpt35_input_price
            output_cost = (Decimal(record.tokens_out) / Decimal("1000")) * openai_gpt35_output_price
            baseline_cost += input_cost + output_cost

        baseline_cost_float = float(baseline_cost)
        savings = baseline_cost_float - actual_cost
        savings_percentage = (
            (savings / baseline_cost_float * 100) if baseline_cost_float > 0 else 0.0
        )

        # Get provider information
        providers = [
            ProviderInfo(
                name="openai",
                display_name="OpenAI",
                description="Reliable general performance",
                models=["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
                pricing_note="$0.0015/1K input, $0.002/1K output (GPT-3.5)",
                speed_rating="fastest",
                cost_rating="moderate",
                icon_color="#10a37f",  # OpenAI green
            ),
            ProviderInfo(
                name="deepseek",
                display_name="DeepSeek",
                description="Cost-effective operations",
                models=["deepseek-chat", "deepseek-coder"],
                pricing_note="$0.00014/1K input, $0.00028/1K output",
                speed_rating="fast",
                cost_rating="cheapest",
                icon_color="#f59e0b",  # Orange
            ),
            ProviderInfo(
                name="huggingface",
                display_name="HuggingFace",
                description="Open-source models",
                models=["llama-3", "mixtral", "qwen"],
                pricing_note="Free (via Inference API)",
                speed_rating="moderate",
                cost_rating="free",
                icon_color="#8b5cf6",  # Purple
            ),
        ]

        return OverviewStatsResponse(
            total_routed_requests=total_requests,
            aggregated_savings_usd=max(0.0, savings),  # Don't show negative savings
            integrated_providers=len(providers),
            current_cost_usd=actual_cost,
            savings_percentage=max(0.0, savings_percentage),
            providers=providers,
        )

    except Exception as e:
        logger.error(f"Error fetching overview stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching overview stats: {str(e)}",
        )


@router.get("/v1/routing/preview", response_model=RoutingPreviewResponse)
async def preview_routing(
    task: Optional[str] = Query(None, description="Task type: summarization, reasoning, general"),
    budget: Optional[str] = Query(None, description="Budget level: low, medium, high"),
    latency_sensitive: bool = Query(False, description="Whether latency is a priority"),
):
    """
    Preview which provider would be selected based on routing settings.

    This endpoint does NOT require authentication as it's just a preview.
    """
    try:
        from app.routing.router import select_provider
        from app.routing.rules import get_provider_fallback_chain

        # Select provider based on settings
        selected_provider = select_provider(
            task=task,
            budget=budget,
            latency_sensitive=latency_sensitive,
        )

        # Get fallback chain
        fallback_chain = get_provider_fallback_chain()
        fallback_names = [p.name for p in fallback_chain]

        # Determine reason
        reason_parts = []
        if task == "summarization":
            reason_parts.append("Task = Summarization")
        elif task == "reasoning":
            reason_parts.append("Task = Reasoning")
        if budget == "low":
            reason_parts.append("Budget = Low")
        elif budget == "high":
            reason_parts.append("Budget = High")
        if latency_sensitive:
            reason_parts.append("Latency Sensitive = True")

        if not reason_parts:
            reason = "Default routing (OpenAI)"
        else:
            reason = "Selected because: " + ", ".join(reason_parts)

        # Provider display names
        display_names = {
            "openai": "OpenAI",
            "deepseek": "DeepSeek",
            "huggingface": "HuggingFace",
        }

        return RoutingPreviewResponse(
            selected_provider=selected_provider.name,
            provider_name=display_names.get(selected_provider.name, selected_provider.name.title()),
            reason=reason,
            fallback_chain=fallback_names,
        )

    except Exception as e:
        logger.error(f"Error previewing routing: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error previewing routing: {str(e)}",
        )


@router.get("/v1/providers", response_model=List[ProviderInfo])
async def get_providers():
    """
    Get list of all available providers with their information.

    This endpoint does NOT require authentication.
    """
    providers = [
        ProviderInfo(
            name="openai",
            display_name="OpenAI",
            description="Reliable general performance. Best for fast responses and high quality.",
            models=["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
            pricing_note="$0.0015/1K input, $0.002/1K output (GPT-3.5). GPT-4: $0.03/$0.06",
            speed_rating="fastest",
            cost_rating="moderate",
            icon_color="#10a37f",
        ),
        ProviderInfo(
            name="deepseek",
            display_name="DeepSeek",
            description="Cost-effective operations. Best for high-volume, cost-sensitive tasks.",
            models=["deepseek-chat", "deepseek-coder"],
            pricing_note="$0.00014/1K input, $0.00028/1K output (cheapest option)",
            speed_rating="fast",
            cost_rating="cheapest",
            icon_color="#f59e0b",
        ),
        ProviderInfo(
            name="huggingface",
            display_name="HuggingFace",
            description="Open-source models. Best for reasoning tasks and cost-free operations.",
            models=["llama-3", "mixtral", "qwen"],
            pricing_note="Free (via Inference API)",
            speed_rating="moderate",
            cost_rating="free",
            icon_color="#8b5cf6",
        ),
    ]
    return providers


# Analytics Dashboard Models
class KPIMetric(BaseModel):
    """Key Performance Indicator metric with trend."""

    value: float
    label: str
    trend_percentage: float  # Positive = increase, negative = decrease
    trend_direction: str  # "up" or "down"


class CostTrendPoint(BaseModel):
    """Single data point for cost trend chart."""

    date: str  # Date in YYYY-MM-DD format
    day_name: str  # Day name (Mon, Tue, etc.)
    cost_usd: float


class ProviderCostBreakdown(BaseModel):
    """Provider cost breakdown for donut chart."""

    provider: str
    cost_usd: float
    percentage: float  # Percentage of total cost
    color: str  # Color code for UI


class AnalyticsDashboardResponse(BaseModel):
    """Analytics dashboard response with KPIs and charts."""

    # KPIs
    total_cost: KPIMetric
    total_requests: KPIMetric
    average_latency: KPIMetric
    tokens_used: KPIMetric

    # Charts
    cost_trend: List[CostTrendPoint]  # Daily cost trend
    cost_by_provider: List[ProviderCostBreakdown]  # Provider breakdown with percentages

    # Time range info
    period: str  # "1D", "7D", "30D", "ALL"
    start_date: Optional[datetime]
    end_date: Optional[datetime]


class TransactionRecord(BaseModel):
    """Transaction record for recent transactions table."""

    id: str
    timestamp: datetime
    provider: str
    model: str
    tokens: int  # Total tokens (input + output)
    cost_usd: float
    latency_ms: int


class RecentTransactionsResponse(BaseModel):
    """Recent transactions response."""

    transactions: List[TransactionRecord]
    total: int


@router.get("/v1/analytics", response_model=AnalyticsDashboardResponse)
async def get_analytics_dashboard(
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db),
    period: str = Query("7D", description="Time period: 1D, 7D, 30D, ALL"),
):
    """
    Get analytics dashboard data with KPIs, trends, and charts.

    Returns:
    - KPI metrics (total cost, requests, latency, tokens) with trends
    - Daily cost trend data for line chart
    - Cost breakdown by provider for donut chart
    """
    try:
        # Calculate date ranges based on period
        now = datetime.utcnow()
        end_date = now

        if period == "1D":
            start_date = now - timedelta(days=1)
            previous_start = start_date - timedelta(days=1)
            previous_end = start_date
        elif period == "7D":
            start_date = now - timedelta(days=7)
            previous_start = start_date - timedelta(days=7)
            previous_end = start_date
        elif period == "30D":
            start_date = now - timedelta(days=30)
            previous_start = start_date - timedelta(days=30)
            previous_end = start_date
        else:  # ALL
            start_date = None
            previous_start = None
            previous_end = None

        # Build base query for current period
        current_query = db.query(CostRecord).filter(CostRecord.api_key_id == api_key.id)
        if start_date:
            current_query = current_query.filter(CostRecord.created_at >= start_date)
        if end_date:
            current_query = current_query.filter(CostRecord.created_at <= end_date)

        # Build query for previous period (for trend calculation)
        previous_query = db.query(CostRecord).filter(CostRecord.api_key_id == api_key.id)
        if previous_start and previous_end:
            previous_query = previous_query.filter(
                CostRecord.created_at >= previous_start,
                CostRecord.created_at < previous_end,
            )
        else:
            previous_query = previous_query.filter(False)  # No previous period for ALL

        # Calculate current period metrics
        current_summary = current_query.with_entities(
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.count(CostRecord.id).label("total_requests"),
            func.avg(CostRecord.latency_ms).label("avg_latency"),
            func.sum(CostRecord.tokens_in + CostRecord.tokens_out).label("total_tokens"),
        ).first()

        current_cost = float(current_summary.total_cost or 0)
        current_requests = current_summary.total_requests or 0
        current_avg_latency = float(current_summary.avg_latency or 0)
        current_tokens = current_summary.total_tokens or 0

        # Calculate previous period metrics
        previous_summary = previous_query.with_entities(
            func.sum(CostRecord.cost_usd).label("total_cost"),
            func.count(CostRecord.id).label("total_requests"),
            func.avg(CostRecord.latency_ms).label("avg_latency"),
            func.sum(CostRecord.tokens_in + CostRecord.tokens_out).label("total_tokens"),
        ).first()

        previous_cost = float(previous_summary.total_cost or 0) if previous_summary.total_cost else 0
        previous_requests = previous_summary.total_requests or 0
        previous_avg_latency = float(previous_summary.avg_latency or 0) if previous_summary.avg_latency else 0
        previous_tokens = previous_summary.total_tokens or 0

        # Calculate trends (percentage change)
        def calculate_trend(current: float, previous: float) -> Tuple[float, str]:
            if previous == 0:
                return (0.0, "up" if current > 0 else "down")
            change_pct = ((current - previous) / previous) * 100
            return (change_pct, "up" if change_pct >= 0 else "down")

        cost_trend_pct, cost_direction = calculate_trend(current_cost, previous_cost)
        requests_trend_pct, requests_direction = calculate_trend(current_requests, previous_requests)
        latency_trend_pct, latency_direction = calculate_trend(current_avg_latency, previous_avg_latency)
        tokens_trend_pct, tokens_direction = calculate_trend(current_tokens, previous_tokens)

        # For latency, lower is better, so invert the direction
        latency_direction = "down" if latency_direction == "up" else "up"

        # Build KPIs
        kpis = {
            "total_cost": KPIMetric(
                value=current_cost,
                label="TOTAL COST",
                trend_percentage=abs(cost_trend_pct),
                trend_direction=cost_direction,
            ),
            "total_requests": KPIMetric(
                value=float(current_requests),
                label="TOTAL REQUESTS",
                trend_percentage=abs(requests_trend_pct),
                trend_direction=requests_direction,
            ),
            "average_latency": KPIMetric(
                value=current_avg_latency,
                label="AVG. LATENCY",
                trend_percentage=abs(latency_trend_pct),
                trend_direction=latency_direction,
            ),
            "tokens_used": KPIMetric(
                value=float(current_tokens),
                label="TOKENS USED",
                trend_percentage=abs(tokens_trend_pct),
                trend_direction=tokens_direction,
            ),
        }

        # Calculate daily cost trend (for line chart)
        cost_trend_data = []
        if start_date:
            # Get daily aggregations
            daily_query = (
                current_query.with_entities(
                    cast(CostRecord.created_at, Date).label("date"),
                    func.sum(CostRecord.cost_usd).label("daily_cost"),
                )
                .group_by(cast(CostRecord.created_at, Date))
                .order_by(cast(CostRecord.created_at, Date))
            )

            daily_results = daily_query.all()

            # Fill in missing days with zero cost
            current_day = start_date.date()
            end_day = end_date.date()
            daily_dict = {row.date: float(row.daily_cost or 0) for row in daily_results}

            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

            while current_day <= end_day:
                cost_value = daily_dict.get(current_day, 0.0)
                day_name = day_names[current_day.weekday()]
                cost_trend_data.append(
                    CostTrendPoint(
                        date=current_day.isoformat(),
                        day_name=day_name,
                        cost_usd=cost_value,
                    )
                )
                current_day += timedelta(days=1)
        else:
            # For ALL period, show monthly data
            monthly_query = (
                current_query.with_entities(
                    extract("year", CostRecord.created_at).label("year"),
                    extract("month", CostRecord.created_at).label("month"),
                    func.sum(CostRecord.cost_usd).label("monthly_cost"),
                )
                .group_by(
                    extract("year", CostRecord.created_at),
                    extract("month", CostRecord.created_at),
                )
                .order_by(
                    extract("year", CostRecord.created_at),
                    extract("month", CostRecord.created_at),
                )
            )

            monthly_results = monthly_query.all()
            for row in monthly_results:
                date_str = f"{int(row.year)}-{int(row.month):02d}-01"
                cost_trend_data.append(
                    CostTrendPoint(
                        date=date_str,
                        day_name=f"Month {int(row.month)}",
                        cost_usd=float(row.monthly_cost or 0),
                    )
                )

        # Calculate cost by provider (for donut chart)
        provider_query = (
            current_query.with_entities(
                CostRecord.provider,
                func.sum(CostRecord.cost_usd).label("provider_cost"),
            )
            .group_by(CostRecord.provider)
            .order_by(func.sum(CostRecord.cost_usd).desc())
        )

        provider_results = provider_query.all()

        # Provider colors
        provider_colors = {
            "openai": "#10a37f",  # Green
            "deepseek": "#f59e0b",  # Orange
            "huggingface": "#8b5cf6",  # Purple
        }

        provider_breakdown = []
        total_cost_for_percentage = current_cost if current_cost > 0 else 1  # Avoid division by zero

        for row in provider_results:
            provider_cost = float(row.provider_cost or 0)
            percentage = (provider_cost / total_cost_for_percentage) * 100
            provider_breakdown.append(
                ProviderCostBreakdown(
                    provider=row.provider,
                    cost_usd=provider_cost,
                    percentage=percentage,
                    color=provider_colors.get(row.provider.lower(), "#6b7280"),
                )
            )

        return AnalyticsDashboardResponse(
            total_cost=kpis["total_cost"],
            total_requests=kpis["total_requests"],
            average_latency=kpis["average_latency"],
            tokens_used=kpis["tokens_used"],
            cost_trend=cost_trend_data,
            cost_by_provider=provider_breakdown,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

    except Exception as e:
        logger.error(f"Error fetching analytics dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching analytics dashboard: {str(e)}",
        )


@router.get("/v1/transactions/recent", response_model=RecentTransactionsResponse)
async def get_recent_transactions(
    api_key: APIKey = Depends(get_api_key),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100, description="Number of recent transactions to return"),
):
    """
    Get recent API transactions for the transactions table.

    Returns the most recent transactions with timestamp, provider, model,
    tokens, cost, and latency.
    """
    try:
        # Get most recent transactions
        records = (
            db.query(CostRecord)
            .filter(CostRecord.api_key_id == api_key.id)
            .order_by(CostRecord.created_at.desc())
            .limit(limit)
            .all()
        )

        transactions = [
            TransactionRecord(
                id=str(record.id),
                timestamp=record.created_at,
                provider=record.provider,
                model=record.model,
                tokens=record.tokens_in + record.tokens_out,
                cost_usd=float(record.cost_usd),
                latency_ms=record.latency_ms,
            )
            for record in records
        ]

        # Get total count for pagination info
        total_count = (
            db.query(func.count(CostRecord.id))
            .filter(CostRecord.api_key_id == api_key.id)
            .scalar()
            or 0
        )

        return RecentTransactionsResponse(
            transactions=transactions,
            total=total_count,
        )

    except Exception as e:
        logger.error(f"Error fetching recent transactions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching recent transactions: {str(e)}",
        )

