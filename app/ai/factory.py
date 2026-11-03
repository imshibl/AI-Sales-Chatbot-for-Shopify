from __future__ import annotations

from typing import Any

from app.ai.gemini_provider import GeminiProvider
from app.ai.interfaces import AIResponse, LLMProvider
from app.core.config import settings
from app.core.exceptions import AIServiceError


class MockProvider(LLMProvider):
    def generate_response(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> AIResponse:
        return AIResponse(content="I can help you find products from this store.")


def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "mock":
        return MockProvider()
    raise AIServiceError("LLM_PROVIDER must be set to either 'gemini' or 'mock'.")
