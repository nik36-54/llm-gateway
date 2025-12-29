"""HuggingFace Inference API provider adapter."""
import httpx
import uuid
from typing import List, Dict, Any, Optional
from app.providers.base import LLMProvider, ProviderResponse, ProviderError, ProviderTimeoutError, ProviderRateLimitError
from app.config import settings


class HuggingFaceProvider(LLMProvider):
    """HuggingFace Inference API provider implementation."""

    def __init__(self):
        self.api_key = getattr(settings, 'huggingface_api_key', None)
        self.base_url = "https://api-inference.huggingface.co/models"
        self.timeout = settings.provider_timeout
        
        # Supported models
        self.models = {
            "llama-3": "meta-llama/Meta-Llama-3-8B-Instruct",
            "mixtral": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "qwen": "Qwen/Qwen2-7B-Instruct",
        }

    @property
    def name(self) -> str:
        return "huggingface"

    def _get_model_endpoint(self, model: Optional[str] = None) -> str:
        """Get the full model endpoint URL."""
        if model is None:
            model = "llama-3"  # Default model
        
        # Map short names to full model paths
        model_path = self.models.get(model.lower(), model)
        return f"{self.base_url}/{model_path}"

    async def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> ProviderResponse:
        """Send chat completion request to HuggingFace Inference API."""
        if not self.api_key:
            raise ProviderError("HuggingFace API key not configured")

        model_endpoint = self._get_model_endpoint(model)
        request_id = f"hf-{uuid.uuid4().hex[:12]}"

        # Convert messages to prompt format for HuggingFace
        # HuggingFace uses a simple prompt format or chat template
        prompt = self._format_messages(messages)

        payload = {
            "inputs": prompt,
            "parameters": {
                "temperature": temperature,
            },
        }
        if max_tokens is not None:
            payload["parameters"]["max_new_tokens"] = max_tokens
        payload["parameters"].update(kwargs)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    model_endpoint,
                    json=payload,
                    headers=headers,
                )
                
                # HuggingFace returns 503 when model is loading
                if response.status_code == 503:
                    # Try to extract estimated time
                    error_data = response.json() if response.content else {}
                    wait_time = error_data.get("estimated_time", 10)
                    raise ProviderError(
                        f"HuggingFace model is loading. Estimated wait: {wait_time}s"
                    )
                
                response.raise_for_status()
                data = response.json()

                # HuggingFace returns different formats depending on model
                # Handle both array and object responses
                if isinstance(data, list) and len(data) > 0:
                    content = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    content = data.get("generated_text", str(data))
                else:
                    content = str(data)

                # Extract just the new text (remove prompt if included)
                if prompt in content:
                    content = content.replace(prompt, "").strip()

                # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
                # HuggingFace doesn't always return token counts
                tokens_in = len(prompt) // 4
                tokens_out = len(content) // 4

                return ProviderResponse(
                    content=content,
                    model=model or "llama-3",
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    request_id=request_id,
                    finish_reason="stop",
                    metadata={"model_endpoint": model_endpoint},
                )
        except httpx.TimeoutException:
            raise ProviderTimeoutError(
                f"HuggingFace request timed out after {self.timeout}s"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise ProviderRateLimitError("HuggingFace rate limit exceeded")
            elif e.response.status_code == 503:
                raise ProviderError("HuggingFace model is currently unavailable")
            raise ProviderError(
                f"HuggingFace API error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise ProviderError(f"HuggingFace request failed: {str(e)}")

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into a prompt string."""
        # Simple formatting - can be enhanced with chat templates
        formatted = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        
        return "\n".join(formatted) + "\nAssistant:"

