"""Base provider interface for LLM providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ProviderResponse:
    """Standardized response from LLM providers."""

    content: str
    model: str
    tokens_in: int
    tokens_out: int
    request_id: str
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g., 'openai', 'huggingface')."""
        pass

    @abstractmethod
    async def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """
        Send a chat completion request to the provider.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model name to use (provider-specific)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            ProviderResponse with standardized format

        Raises:
            ProviderError: If the request fails
        """
        pass


class ProviderError(Exception):
    """Base exception for provider errors."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when a provider rate limit is exceeded."""

    pass

