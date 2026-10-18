from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., min_length=1)
    language: Literal["en", "ta", "ml", "hi"] = "en"


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[dict]
