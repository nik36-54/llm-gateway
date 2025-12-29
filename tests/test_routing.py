"""Tests for routing logic."""
import pytest
from app.routing.router import select_provider
from app.providers.openai import OpenAIProvider
from app.providers.huggingface import HuggingFaceProvider
from app.providers.deepseek import DeepSeekProvider


def test_select_provider_summarization():
    """Test routing for summarization task."""
    provider = select_provider(task="summarization")
    assert isinstance(provider, DeepSeekProvider)


def test_select_provider_reasoning():
    """Test routing for reasoning task."""
    provider = select_provider(task="reasoning")
    assert isinstance(provider, HuggingFaceProvider)


def test_select_provider_latency_sensitive():
    """Test routing for latency-sensitive requests."""
    provider = select_provider(latency_sensitive=True)
    assert isinstance(provider, OpenAIProvider)


def test_select_provider_budget_low():
    """Test routing for low budget."""
    provider = select_provider(budget="low")
    assert isinstance(provider, DeepSeekProvider)


def test_select_provider_budget_high():
    """Test routing for high budget."""
    provider = select_provider(budget="high")
    assert isinstance(provider, OpenAIProvider)


def test_select_provider_default():
    """Test default routing."""
    provider = select_provider()
    assert isinstance(provider, OpenAIProvider)

