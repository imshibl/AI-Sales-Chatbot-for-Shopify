"""Adapt chat history and tool declarations to Google's Gemini Gen AI SDK."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from app.ai.interfaces import AIResponse, LLMProvider, ToolCall
from app.core.config import settings
from app.core.exceptions import AIServiceError

logger = logging.getLogger(__name__)
SYSTEM_PROMPT_PATH = Path(__file__).with_name("system_prompt.md")


# Combine the store-specific instruction with per-conversation language preferences.
def _system_instruction(messages: list[dict[str, Any]]) -> str:
    try:
        instruction = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        logger.exception("Unable to load the Gemini system instruction.")
        raise AIServiceError("The assistant is temporarily unavailable. Please try again shortly.") from exc
    instruction = instruction.replace("{{STORE_NAME}}", settings.store_name)
    preferences = [
        message["content"].strip()
        for message in messages
        if message.get("role") == "system" and message.get("content")
    ]
    if preferences:
        instruction += "\n\nConversation preferences:\n" + "\n".join(preferences)
    return instruction

# Convert the app's provider-neutral history into Gemini content and function parts.
def _gemini_contents(messages: list[dict[str, Any]], types: Any) -> list[Any]:
    contents = []
    for message in messages:
        role = message.get("role")
        if role in {"user", "assistant"}:
            parts = []
            if message.get("content"):
                parts.append(types.Part(text=str(message["content"])))
            for call in message.get("tool_calls", []):
                parts.append(
                    types.Part(
                        function_call=types.FunctionCall(
                            id=call.get("call_id") or None,
                            name=call["name"],
                            args=call.get("arguments", {}),
                        ),
                        thought_signature=(
                            base64.b64decode(call["thought_signature"])
                            if call.get("thought_signature")
                            else None
                        ),
                    )
                )
            if parts:
                contents.append(types.Content(role="model" if role == "assistant" else "user", parts=parts))
        elif role == "tool":
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=message.get("call_id") or None,
                                name=message["name"],
                                response={"result": message.get("content")},
                            )
                        )
                    ],
                )
            )
    return contents


class GeminiProvider(LLMProvider):
    """Call Gemini and convert its text/tool response back to app types."""

    def __init__(self) -> None:
        if not settings.gemini_api_key.strip():
            raise AIServiceError("Gemini is selected, but GEMINI_API_KEY is not configured.")
        if not settings.gemini_model.strip():
            raise AIServiceError("Gemini is selected, but GEMINI_MODEL is not configured.")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - dependency is declared in requirements.txt
            logger.exception("Google Gen AI SDK is unavailable.")
            raise AIServiceError("The Gemini client is unavailable. Install the project dependencies and try again.") from exc

        self._types = types
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=20_000),
        )
        self._model = settings.gemini_model

    def generate_response(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AIResponse:
        # Disable automatic tool execution; every action must pass through ToolExecutor.
        gemini_tools = None
        if tools:
            declarations = [
                self._types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool["description"],
                    parameters=tool["parameters"],
                )
                for tool in tools
            ]
            gemini_tools = [self._types.Tool(function_declarations=declarations)]

        config = self._types.GenerateContentConfig(
            system_instruction=_system_instruction(messages),
            tools=gemini_tools,
            automatic_function_calling=self._types.AutomaticFunctionCallingConfig(disable=True),
        )
        # Send normalized history and tool schemas; app code executes returned tool calls.
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=_gemini_contents(messages, self._types),
                config=config,
            )
        except Exception as exc:
            logger.exception("Gemini response generation failed.")
            status_code = getattr(exc, "status_code", getattr(exc, "code", None))
            if status_code == 429:
                message = "Gemini is receiving too many requests right now. Please wait a moment and try again."
            elif status_code == 404:
                message = "The configured Gemini model is unavailable. Check GEMINI_MODEL in .env; no other model was selected."
            elif status_code in {401, 403}:
                message = "Gemini rejected the configured API key. Check GEMINI_API_KEY in .env."
            elif "timeout" in type(exc).__name__.lower():
                message = "The shopping assistant took too long to respond. Please try again."
            else:
                message = "I'm having trouble reaching the shopping assistant right now. Please try again in a moment."
            raise AIServiceError(
                message
            ) from exc

        # Reject empty/malformed provider output instead of fabricating a response.
        candidate = next(
            (
                item
                for item in (response.candidates or [])
                if item.content is not None
            ),
            None,
        )
        if candidate is None:
            logger.error("Gemini returned no response candidate.")
            raise AIServiceError(
                "I couldn't prepare a response just now. Please try again or browse the catalog."
            )

        # Split provider output into plain text and validated structured action requests.
        content_parts = candidate.content.parts or []
        text = "\n".join(part.text for part in content_parts if part.text).strip()
        calls = []
        try:
            for part in content_parts:
                function_call = part.function_call
                if not function_call or not function_call.name:
                    continue
                arguments = function_call.args or {}
                if not isinstance(arguments, dict):
                    raise TypeError("Gemini returned non-object tool arguments.")
                calls.append(
                    ToolCall(
                        name=function_call.name,
                        arguments=arguments,
                        call_id=function_call.id or "",
                        thought_signature=(
                            base64.b64encode(part.thought_signature).decode("ascii")
                            if part.thought_signature
                            else None
                        ),
                    )
                )
        except (AttributeError, TypeError, ValueError) as exc:
            logger.exception("Gemini returned malformed function-call data.")
            raise AIServiceError(
                "The assistant returned an invalid action request. Please try asking another way."
            ) from exc
        if not text and not calls:
            logger.error("Gemini returned an empty response.")
            raise AIServiceError(
                "I couldn't prepare a response just now. Please try again or browse the catalog."
            )
        return AIResponse(content=text, tool_calls=calls)
