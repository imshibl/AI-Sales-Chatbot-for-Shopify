"""Provider-neutral message, tool-call, and language-model contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """Represent one model-requested action for the backend tool executor."""
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    thought_signature: str | None = None


@dataclass
class AIResponse:
    """Carry assistant text and any structured tool requests."""
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    """Interface implemented by mock and external language-model providers."""
    @abstractmethod
    def generate_response(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AIResponse:
        raise NotImplementedError
