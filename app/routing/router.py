"""Deterministic routing engine for selecting LLM providers."""
from typing import Optional
from app.providers.base import LLMProvider
from app.routing.rules import select_provider_by_name, get_provider_fallback_chain


def select_provider(
    task: Optional[str] = None,
    budget: Optional[str] = None,
    latency_sensitive: bool = False,
    provider_override: Optional[str] = None,
) -> LLMProvider:
    """
    Deterministically select a provider based on routing rules.

    Routing priority:
    1. If provider_override is specified, use that provider
    2. If task == "summarization", use DeepSeek (low cost)
    3. If task == "reasoning", use HuggingFace (open-source models)
    4. If latency_sensitive == True, use OpenAI (fastest)
    5. If budget == "low", use DeepSeek
    6. If budget == "high", use OpenAI
    7. Default to OpenAI

    Args:
        task: Task type (summarization, reasoning, general)
        budget: Budget level (low, medium, high)
        latency_sensitive: Whether latency is a priority
        provider_override: Optional provider name to override routing

    Returns:
        Selected LLMProvider instance
    """
    # Override takes highest priority
    if provider_override:
        return select_provider_by_name(provider_override)

    # Task-based routing
    if task == "summarization":
        return select_provider_by_name("deepseek")  # Low cost
    elif task == "reasoning":
        return select_provider_by_name("huggingface")  # Open-source models

    # Latency-sensitive routing
    if latency_sensitive:
        return select_provider_by_name("openai")  # Fastest

    # Budget-based routing
    if budget == "low":
        return select_provider_by_name("deepseek")
    elif budget == "high":
        return select_provider_by_name("openai")

    # Default
    return select_provider_by_name("openai")

