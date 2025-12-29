"""Deterministic routing rules for LLM providers."""
from typing import List
from app.providers.base import LLMProvider
from app.providers.openai import OpenAIProvider
from app.providers.deepseek import DeepSeekProvider
from app.providers.huggingface import HuggingFaceProvider


def get_all_providers() -> List[LLMProvider]:
    """Get all available providers."""
    return [
        OpenAIProvider(),
        DeepSeekProvider(),
        HuggingFaceProvider(),
    ]


def get_provider_fallback_chain() -> List[LLMProvider]:
    """
    Get the fallback chain for providers.
    Returns providers in order of preference for fallback scenarios.
    """
    return [
        OpenAIProvider(),  # Primary fallback (fast, reliable)
        DeepSeekProvider(),  # Secondary fallback (cheap)
        HuggingFaceProvider(),  # Tertiary fallback (open-source)
    ]


def select_provider_by_name(name: str) -> LLMProvider:
    """Select a provider by name."""
    providers = {
        "openai": OpenAIProvider,
        "deepseek": DeepSeekProvider,
        "huggingface": HuggingFaceProvider,
        "hf": HuggingFaceProvider,  # Alias
    }
    provider_class = providers.get(name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {name}")
    return provider_class()

