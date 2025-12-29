"""Tests for cost calculation."""
import pytest
from decimal import Decimal
from app.cost.tracker import calculate_cost


def test_calculate_cost_openai_gpt4():
    """Test cost calculation for OpenAI GPT-4."""
    cost = calculate_cost("openai", "gpt-4", 1000, 500)
    # 1K input tokens * $0.03 + 0.5K output tokens * $0.06 = $0.03 + $0.03 = $0.06
    expected = Decimal("0.06")
    assert abs(cost - expected) < Decimal("0.001")


def test_calculate_cost_openai_gpt35():
    """Test cost calculation for OpenAI GPT-3.5."""
    cost = calculate_cost("openai", "gpt-3.5-turbo", 1000, 500)
    # 1K input tokens * $0.0015 + 0.5K output tokens * $0.002 = $0.0015 + $0.001 = $0.0025
    expected = Decimal("0.0025")
    assert abs(cost - expected) < Decimal("0.001")


def test_calculate_cost_huggingface():
    """Test cost calculation for HuggingFace (free tier)."""
    cost = calculate_cost("huggingface", "llama-3", 1000, 500)
    # HuggingFace is free, cost should be 0
    expected = Decimal("0.0")
    assert cost == expected


def test_calculate_cost_deepseek():
    """Test cost calculation for DeepSeek."""
    cost = calculate_cost("deepseek", "deepseek-chat", 1000, 500)
    # 1K input tokens * $0.00014 + 0.5K output tokens * $0.00028 = $0.00014 + $0.00014 = $0.00028
    expected = Decimal("0.00028")
    assert abs(cost - expected) < Decimal("0.0001")


def test_calculate_cost_unknown_provider():
    """Test cost calculation for unknown provider returns zero."""
    cost = calculate_cost("unknown", "unknown-model", 1000, 500)
    assert cost == Decimal("0")

