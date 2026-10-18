from google import genai
from google.genai import types
import pytest

from app.ai.gemini_provider import GeminiProvider
from app.ai.interfaces import AIResponse, ToolCall
from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.repositories.memory import MemoryRepository
from app.services.chat_service import ChatService


class FakeToolProvider:
    def __init__(self, tool_call: ToolCall):
        self.tool_call = tool_call
        self.calls = 0

    def generate_response(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return AIResponse(content="", tool_calls=[self.tool_call])
        return AIResponse(content="I found an option from the catalog.")


def test_chat_executes_gemini_catalog_tools_and_uses_real_product_cards():
    repository = MemoryRepository()
    provider = FakeToolProvider(
        ToolCall(
            name="get_product_recommendations",
            arguments={"skin_type": "oily", "concern": "acne marks", "max_price": 1000},
            call_id="recommend-1",
        )
    )
    chat = ChatService(repository=repository, llm_provider=provider)

    response = chat.handle_message(None, "I have oily skin and acne marks under ₹1,000")

    assert provider.calls == 2
    assert response["response"] == "I found an option from the catalog."
    assert [card["id"] for card in response["product_cards"]] == ["prod_001"]
    assert response["product_cards"][0]["price"] == repository.get_product("prod_001")["price"]
    stored = repository.get_conversation(response["conversation_id"])["messages"][-1]
    assert stored["tool_steps"][0]["tool_calls"][0]["name"] == "get_product_recommendations"


@pytest.mark.parametrize(
    ("language", "language_name"),
    [("ta", "Tamil"), ("ml", "Malayalam"), ("hi", "Hindi")],
)
def test_chat_passes_selected_language_as_a_system_preference(language, language_name):
    class LanguageAwareProvider:
        def generate_response(self, messages, tools=None):
            preference = next(message["content"] for message in messages if message["role"] == "system")
            assert language_name in preference
            assert "Manglish" in preference
            assert "Tanglish" in preference
            assert "Hinglish" in preference
            assert "Latin transliteration" in preference
            assert "mirror their natural balance" in preference
            return AIResponse(content="localized response")

    chat = ChatService(repository=MemoryRepository(), llm_provider=LanguageAwareProvider())
    response = chat.handle_message(None, "hello", language=language)

    assert response["response"] == "localized response"


def test_malformed_gemini_cart_tool_arguments_do_not_mutate_cart():
    repository = MemoryRepository()
    provider = FakeToolProvider(
        ToolCall(
            name="add_to_cart",
            arguments={"product_id": "prod_001", "quantity": 0},
            call_id="add-1",
        )
    )
    chat = ChatService(repository=repository, llm_provider=provider)

    response = chat.handle_message(None, "Add one cleanser to my cart")

    assert response["cart"] == {}
    tool_result = response["response"]
    assert tool_result == "I found an option from the catalog."
    history = repository.get_conversation(response["conversation_id"])["messages"][-1]
    assert "invalid arguments" in history["tool_steps"][0]["results"][0]["content"]


def test_completed_cart_action_is_reported_if_followup_generation_fails():
    class ProviderUnavailableAfterTool(FakeToolProvider):
        def generate_response(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return AIResponse(content="", tool_calls=[self.tool_call])
            raise AIServiceError("Gemini is unavailable.")

    repository = MemoryRepository()
    provider = ProviderUnavailableAfterTool(
        ToolCall(
            name="add_to_cart",
            arguments={"product_id": "prod_001", "quantity": 1},
            call_id="add-1",
        )
    )
    chat = ChatService(repository=repository, llm_provider=provider)

    response = chat.handle_message(None, "Add the cleanser to my cart")

    assert response["cart"]["prod_001"]["quantity"] == 1
    assert "updated successfully" in response["response"]
    assert "temporarily unavailable" in response["response"]


def test_gemini_adapter_uses_sdk_tools_without_network(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "test-free-model")

    class FakeModels:
        def __init__(self):
            self.calls = 0

        def generate_content(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                parts = [types.Part(function_call=types.FunctionCall(
                    id="sdk-call-1",
                    name="get_product_details",
                    args={"product_id": "prod_001"},
                ), thought_signature=b"opaque-test-signature")]
            else:
                model_message = next(item for item in kwargs["contents"] if item.role == "model")
                assert model_message.parts[0].thought_signature == b"opaque-test-signature"
                assert "Tamil" in kwargs["config"].system_instruction
                parts = [types.Part(text="Here are the verified product details.")]
            return types.GenerateContentResponse(
                candidates=[types.Candidate(content=types.Content(role="model", parts=parts))]
            )

    class FakeClient:
        def __init__(self):
            self.models = FakeModels()

    client = FakeClient()
    monkeypatch.setattr(genai, "Client", lambda **kwargs: client)
    provider = GeminiProvider()
    tools = [{
        "name": "get_product_details",
        "description": "Get a product.",
        "parameters": {"type": "OBJECT", "properties": {"product_id": {"type": "STRING"}}, "required": ["product_id"]},
    }]

    first_response = provider.generate_response([{"role": "user", "content": "Tell me about the cleanser."}], tools)
    final_response = provider.generate_response(
        [
            {"role": "user", "content": "Tell me about the cleanser."},
            {"role": "assistant", "content": "", "tool_calls": [{
                "name": first_response.tool_calls[0].name,
                "arguments": first_response.tool_calls[0].arguments,
                "call_id": first_response.tool_calls[0].call_id,
                "thought_signature": first_response.tool_calls[0].thought_signature,
            }]},
            {"role": "tool", "name": "get_product_details", "call_id": "sdk-call-1", "content": "{\"product\": {}}"},
            {"role": "system", "content": "Reply to the customer in Tamil."},
        ],
        tools,
    )

    assert first_response.tool_calls == [
        ToolCall(
            name="get_product_details",
            arguments={"product_id": "prod_001"},
            call_id="sdk-call-1",
            thought_signature="b3BhcXVlLXRlc3Qtc2lnbmF0dXJl",
        )
    ]
    assert final_response.content == "Here are the verified product details."
    assert client.models.calls == 2
