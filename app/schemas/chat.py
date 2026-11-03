"""Request and response models for chat messages and conversation history."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Validate a customer message and its optional conversation/language."""

    conversation_id: str | None = None
    message: str = Field(..., min_length=1)
    language: Literal["en", "ta", "ml", "hi"] = "en"


class ChatHistoryResponse(BaseModel):
    """Return stored turns for one conversation."""

    conversation_id: str
    messages: list[dict]
