"""HTTP endpoints for sending chat turns and managing conversation history."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.exceptions import AppError
from app.repositories.factory import repository as repo
from app.schemas.chat import ChatHistoryResponse, ChatMessageRequest
from app.services.chat_service import ChatService

router = APIRouter()
service = ChatService(repo)

# Chat generation and its domain errors are handled by the service layer.
@router.post("/chat")
def chat(payload: ChatMessageRequest):
    try:
        return service.handle_message(
            payload.conversation_id,
            payload.message,
            language=payload.language,
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc

# History and deletion use the shared repository directly because they are record reads.
@router.get("/chat/{conversation_id}/history")
def chat_history(conversation_id: str):
    conversation = repo.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail={"message": f"Conversation '{conversation_id}' was not found.", "error_code": "not_found"})
    return ChatHistoryResponse(conversation_id=conversation_id, messages=conversation.get("messages", []))


@router.delete("/chat/{conversation_id}")
def clear_chat(conversation_id: str):
    try:
        repo.delete_conversation(conversation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"message": f"Conversation '{conversation_id}' was not found.", "error_code": "not_found"})
    return {"status": "deleted", "conversation_id": conversation_id}
