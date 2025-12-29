"""OpenAI provider adapter."""
import httpx
import uuid
from typing import List, Dict, Any, Optional
from app.providers.base import LLMProvider, ProviderResponse, ProviderError, ProviderTimeoutError, ProviderRateLimitError
from app.config import settings


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = "https://api.openai.com/v1"
        self.timeout = settings.provider_timeout

    @property
    def name(self) -> str:
        return "openai"

    async def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """Send chat completion request to OpenAI."""
        if not self.api_key:
            raise ProviderError("OpenAI API key not configured")

        if model is None:
            model = "gpt-3.5-turbo"

        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                choice = data["choices"][0]
                usage = data.get("usage", {})
                content = choice["message"]["content"]
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
                finish_reason = choice.get("finish_reason")

                return ProviderResponse(
                    content=content,
                    model=data["model"],
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    request_id=data.get("id", request_id),
                    finish_reason=finish_reason,
                    metadata={"response_id": data.get("id")},
                )
        except httpx.TimeoutException:
            raise ProviderTimeoutError(f"OpenAI request timed out after {self.timeout}s")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise ProviderRateLimitError("OpenAI rate limit exceeded")
            raise ProviderError(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise ProviderError(f"OpenAI request failed: {str(e)}")

