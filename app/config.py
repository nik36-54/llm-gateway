"""Configuration management using Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    database_url: str = "postgresql://postgres:postgres@localhost:5432/llm_gateway"

    # Provider API Keys
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None

    # Security
    secret_key: str = "change-me-in-production"

    # Logging
    log_level: str = "INFO"
    environment: str = "dev"

    # Provider timeouts (in seconds)
    provider_timeout: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()

