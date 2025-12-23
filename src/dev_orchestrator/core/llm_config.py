"""LLM configuration and client management.

Handles OpenAI setup with environment variables.
Never stores secrets in code.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load .env file if present
load_dotenv()


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    # OpenAI settings
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 4096

    # Rate limiting
    max_retries: int = 3
    request_timeout: int = 60

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables."""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "4096")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
            request_timeout=int(os.getenv("OPENAI_TIMEOUT", "60")),
        )

    def validate(self) -> bool:
        """Check if configuration is valid."""
        if not self.openai_api_key:
            return False
        if not self.openai_api_key.startswith("sk-"):
            return False
        return True


@lru_cache(maxsize=1)
def get_llm_config() -> LLMConfig:
    """Get cached LLM configuration."""
    return LLMConfig.from_env()


def create_chat_model(
    config: LLMConfig | None = None,
    temperature: float | None = None,
    model: str | None = None,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance.

    Args:
        config: LLM configuration (uses default if None)
        temperature: Override temperature
        model: Override model name

    Returns:
        Configured ChatOpenAI instance

    Raises:
        ValueError: If API key is not configured
    """
    if config is None:
        config = get_llm_config()

    if not config.validate():
        raise ValueError(
            "OpenAI API key not configured. "
            "Set OPENAI_API_KEY environment variable or create .env file."
        )

    return ChatOpenAI(
        api_key=config.openai_api_key,
        model=model or config.openai_model,
        temperature=temperature if temperature is not None else config.temperature,
        max_tokens=config.max_tokens,
        max_retries=config.max_retries,
        request_timeout=config.request_timeout,
    )


def check_llm_available() -> tuple[bool, str]:
    """Check if LLM is available and configured.

    Returns:
        Tuple of (is_available, message)
    """
    config = get_llm_config()

    if not config.openai_api_key:
        return False, "OPENAI_API_KEY not set"

    if not config.openai_api_key.startswith("sk-"):
        return False, "Invalid API key format"

    # Try to create client
    try:
        llm = create_chat_model(config)
        # Quick validation - just check client creation
        return True, f"OpenAI configured with model {config.openai_model}"
    except Exception as e:
        return False, f"Failed to create LLM client: {e}"
