"""LLM provider abstraction with env-based configuration and fallback support."""
import os
import logging
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM instances with configurable providers.

    Supported providers (set via LLM_PROVIDER env):
      - "openrouter" (default): uses OPENROUTER_API_KEY, LLM_BASE_URL
      - "openai": uses OPENAI_API_KEY, standard OpenAI endpoint

    Environment variables:
      LLM_PROVIDER      — provider name (default: "openrouter")
      LLM_BASE_URL      — custom API base URL (default: https://openrouter.ai/api/v1)
      LLM_TIMEOUT       — request timeout in seconds (default: 120)
      TRIAGE_MODEL      — default model name (default: google/gemini-2.0-flash-001)
    """

    PROVIDERS = {
        "openrouter": {
            "api_key_env": "OPENROUTER_API_KEY",
        },
        "openai": {
            "api_key_env": "OPENAI_API_KEY",
        },
    }

    @classmethod
    def create(cls, model: str = None, temperature: float = 0.3, **kwargs):
        """Create a ChatOpenAI instance configured for the selected provider.

        Args:
            model: Model name (defaults to TRIAGE_MODEL env or fallback).
            temperature: LLM temperature setting.
            **kwargs: Additional arguments passed to ChatOpenAI.

        Returns:
            Configured ChatOpenAI instance.

        Raises:
            ValueError: If LLM_PROVIDER is unknown.
        """
        provider = os.getenv("LLM_PROVIDER", "openrouter")
        config = cls.PROVIDERS.get(provider)

        if not config:
            raise ValueError(
                f"Unknown LLM provider: '{provider}'. "
                f"Supported: {', '.join(cls.PROVIDERS)}"
            )

        api_key = os.getenv(config["api_key_env"])
        if not api_key:
            logger.warning(
                "%s not set for provider '%s'",
                config["api_key_env"], provider
            )

        # Determine base URL per provider
        base_url = os.getenv("LLM_BASE_URL", None)
        if provider == "openrouter" and not base_url:
            base_url = "https://openrouter.ai/api/v1"

        return ChatOpenAI(
            model=model or os.getenv("TRIAGE_MODEL", "google/gemini-2.0-flash-001"),
            openai_api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            request_timeout=int(os.getenv("LLM_TIMEOUT", "120")),
            **kwargs
        )
