"""Cost tracking and calculation for LLM requests."""
from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.cost.models import CostRecord, APIKey
from app.providers.base import ProviderResponse


# Pricing per 1K tokens (input and output)
# HuggingFace Inference API is free for most models, but we set a nominal cost for tracking
PRICING = {
    "openai": {
        "gpt-4": {"input": Decimal("0.03"), "output": Decimal("0.06")},
        "gpt-4-turbo-preview": {"input": Decimal("0.01"), "output": Decimal("0.03")},
        "gpt-3.5-turbo": {"input": Decimal("0.0015"), "output": Decimal("0.002")},
        "gpt-3.5-turbo-16k": {"input": Decimal("0.003"), "output": Decimal("0.004")},
    },
    "deepseek": {
        "deepseek-chat": {"input": Decimal("0.00014"), "output": Decimal("0.00028")},
        "deepseek-coder": {"input": Decimal("0.00014"), "output": Decimal("0.00028")},
    },
    "huggingface": {
        "llama-3": {"input": Decimal("0.0"), "output": Decimal("0.0")},  # Free tier
        "mixtral": {"input": Decimal("0.0"), "output": Decimal("0.0")},  # Free tier
        "qwen": {"input": Decimal("0.0"), "output": Decimal("0.0")},  # Free tier
        "meta-llama/Meta-Llama-3-8B-Instruct": {"input": Decimal("0.0"), "output": Decimal("0.0")},
        "mistralai/Mixtral-8x7B-Instruct-v0.1": {"input": Decimal("0.0"), "output": Decimal("0.0")},
        "Qwen/Qwen2-7B-Instruct": {"input": Decimal("0.0"), "output": Decimal("0.0")},
    },
}


def calculate_cost(
    provider: str, model: str, tokens_in: int, tokens_out: int
) -> Decimal:
    """
    Calculate cost in USD for a request.

    Args:
        provider: Provider name (openai, deepseek, huggingface)
        model: Model name
        tokens_in: Input tokens
        tokens_out: Output tokens

    Returns:
        Cost in USD as Decimal
    """
    provider_pricing = PRICING.get(provider, {})
    model_pricing = provider_pricing.get(model)

    if not model_pricing:
        # Try to find a similar model (fallback to first model in provider)
        if provider_pricing:
            model_pricing = next(iter(provider_pricing.values()))
        else:
            # Default pricing if unknown
            return Decimal("0")

    input_cost_per_1k = model_pricing["input"]
    output_cost_per_1k = model_pricing["output"]

    # Calculate cost: (tokens / 1000) * cost_per_1k
    input_cost = (Decimal(tokens_in) / Decimal("1000")) * input_cost_per_1k
    output_cost = (Decimal(tokens_out) / Decimal("1000")) * output_cost_per_1k

    return input_cost + output_cost


def record_cost(
    db: Session,
    api_key: APIKey,
    provider_response: ProviderResponse,
    request_id: str,
    latency_ms: int,
) -> CostRecord:
    """
    Record cost information to the database.

    Args:
        db: Database session
        api_key: API key record
        provider_response: Provider response with token usage
        request_id: Request identifier
        latency_ms: Request latency in milliseconds

    Returns:
        Created CostRecord
    """
    # Determine provider name from model name
    model_lower = provider_response.model.lower()
    if "gpt" in model_lower:
        provider = "openai"
    elif "deepseek" in model_lower:
        provider = "deepseek"
    elif "llama" in model_lower or "mixtral" in model_lower or "qwen" in model_lower:
        provider = "huggingface"
    else:
        provider = "unknown"

    cost_usd = calculate_cost(
        provider,
        provider_response.model,
        provider_response.tokens_in,
        provider_response.tokens_out,
    )

    cost_record = CostRecord(
        api_key_id=api_key.id,
        request_id=request_id,
        provider=provider,
        model=provider_response.model,
        tokens_in=provider_response.tokens_in,
        tokens_out=provider_response.tokens_out,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        created_at=datetime.utcnow(),
    )

    db.add(cost_record)
    db.commit()
    db.refresh(cost_record)

    return cost_record

