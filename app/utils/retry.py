"""Retry logic with exponential backoff and provider fallback."""
import asyncio
import time
from typing import List, Optional, Callable, Any
from app.providers.base import LLMProvider, ProviderError, ProviderTimeoutError, ProviderRateLimitError
from app.routing.rules import get_provider_fallback_chain


async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    **kwargs: Any
) -> Any:
    """
    Retry a function with exponential backoff.

    Args:
        func: Async function to retry
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        **kwargs: Arguments to pass to func

    Returns:
        Result of func

    Raises:
        Last exception if all attempts fail
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(max_attempts):
        try:
            return await func(**kwargs)
        except (ProviderTimeoutError, ProviderError) as e:
            last_exception = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
                delay = min(delay * exponential_base, max_delay)
            else:
                raise
        except Exception as e:
            # For non-provider errors, don't retry
            raise

    if last_exception:
        raise last_exception


async def call_with_fallback(
    providers: List[LLMProvider],
    messages: List[dict],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    **kwargs: Any
) -> tuple:
    """
    Call LLM provider with fallback chain.

    Args:
        providers: List of providers to try in order
        messages: Chat messages
        model: Model name (optional)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        **kwargs: Additional provider parameters

    Returns:
        Tuple of (ProviderResponse, provider_name, fallback_used)

    Raises:
        ProviderError: If all providers fail
    """
    last_exception = None
    fallback_used = False

    for i, provider in enumerate(providers):
        try:
            response = await provider.chat_completions(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response, provider.name, fallback_used
        except (ProviderTimeoutError, ProviderRateLimitError, ProviderError) as e:
            last_exception = e
            if i < len(providers) - 1:
                fallback_used = True
                # Short delay before trying next provider
                await asyncio.sleep(0.5)
            else:
                # All providers exhausted
                raise
        except Exception as e:
            # Unexpected error, don't retry
            raise ProviderError(f"Unexpected error from {provider.name}: {str(e)}")

    if last_exception:
        raise last_exception
    raise ProviderError("No providers available")

