from __future__ import annotations

from app.adapters.providers.anthropic import AnthropicProvider
from app.adapters.providers.base import LLMProvider
from app.adapters.providers.mock import MockProvider
from app.core.settings import Settings


def provider_from_settings(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockProvider()
    if settings.llm_provider == "anthropic":
        return AnthropicProvider()
    raise ValueError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}")
