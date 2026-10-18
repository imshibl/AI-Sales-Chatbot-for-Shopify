from google import genai
from google.genai import types
import pytest

from app.ai.gemini_provider import GeminiProvider
from app.ai.interfaces import AIResponse, ToolCall
from app.core.config import settings
from app.core.exceptions import AIServiceError, ConflictError
from app.repositories.memory import MemoryRepository
from app.services.cart_service import CartService
from app.services.chat_service import ChatService
from app.services.order_service import OrderService


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


def test_assistant_prepares_order_then_places_it_after_later_explicit_confirmation():
    repository = MemoryRepository()
    conversation_id = "conv_ai_checkout_test"
    repository.create_conversation({
        "conversation_id": conversation_id,
        "customer_id": repository.demo_customer_id,
        "messages": [],
        "cart": {},
    })
    CartService(repository).add_item(conversation_id, "prod_001", 1)
    provider_responses = [
        AIResponse(content="", tool_calls=[ToolCall(
            name="prepare_order",
            arguments={
                "customer_name": "Anu Thomas",
                "email": "anu@example.com",
                "phone": "+91 98765 43210",
                "shipping_address": "12 Lotus Avenue, Bengaluru, Karnataka 560001",
            },
        )]),
        AIResponse(content="The total is ready. Please confirm before I place the order."),
        AIResponse(content="", tool_calls=[ToolCall(name="place_order", arguments={})]),
        AIResponse(content="Your demo order is ready with a payment link."),
    ]

    class CheckoutProvider:
        def generate_response(self, messages, tools=None):
            return provider_responses.pop(0)

    chat = ChatService(repository=repository, llm_provider=CheckoutProvider())
    prepared = chat.handle_message(
        conversation_id,
        "I want to order. My name is Anu Thomas, email anu@example.com, phone +91 98765 43210, address 12 Lotus Avenue, Bengaluru, Karnataka 560001.",
    )
    assert repository.get_order_by_customer(repository.demo_customer_id) == []
    assert repository.get_conversation(conversation_id)["pending_checkout"]["customer_name"] == "Anu Thomas"

    placed = chat.handle_message(conversation_id, "Yes, place the order.")

    assert prepared["response"] == "The total is ready. Please confirm before I place the order."
    assert placed["order"]["id"].startswith("TN-")
    assert placed["payment_link"] == placed["order"]["payment_url"]
    assert placed["payment_link"] in placed["response"]
    order = repository.get_order(placed["order"]["id"])
    assert order["payment_status"] == "pending"
    assert order["customer_name"] == "Anu Thomas"
    assert order["email"] == "anu@example.com"
    assert order["phone"] == "+91 98765 43210"
    assert order["shipping_address"] == "12 Lotus Avenue, Bengaluru, Karnataka 560001"
    assert repository.get_conversation(conversation_id)["pending_checkout"] is None
    assert repository.get_conversation(conversation_id)["cart"] == {}


def test_order_cannot_be_placed_in_same_turn_as_checkout_preparation():
    repository = MemoryRepository()
    conversation_id = "conv_same_turn_checkout_test"
    repository.create_conversation({
        "conversation_id": conversation_id,
        "customer_id": repository.demo_customer_id,
        "messages": [],
        "cart": {},
    })
    CartService(repository).add_item(conversation_id, "prod_001", 1)

    class SameTurnProvider:
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return AIResponse(content="", tool_calls=[ToolCall(
                    name="prepare_order",
                    arguments={
                        "customer_name": "Anu Thomas",
                        "email": "anu@example.com",
                        "phone": "+91 98765 43210",
                        "shipping_address": "12 Lotus Avenue, Bengaluru, Karnataka 560001",
                    },
                )])
            if self.calls == 2:
                return AIResponse(content="", tool_calls=[ToolCall(name="place_order", arguments={})])
            assert "later message" in next(
                tool["description"] for tool in tools if tool["name"] == "place_order"
            )
            return AIResponse(content="Please review the summary and confirm in your next message.")

    response = ChatService(repository=repository, llm_provider=SameTurnProvider()).handle_message(
        conversation_id,
        "Yes, place this order. My name is Anu Thomas, email anu@example.com, phone +91 98765 43210, address 12 Lotus Avenue, Bengaluru, Karnataka 560001.",
    )

    assert repository.get_order_by_customer(repository.demo_customer_id) == []
    assert "confirm in your next message" in response["response"]


def test_order_requires_reconfirmation_if_cart_changes_after_summary():
    repository = MemoryRepository()
    conversation_id = "conv_changed_cart_checkout_test"
    repository.create_conversation({
        "conversation_id": conversation_id,
        "customer_id": repository.demo_customer_id,
        "messages": [],
        "cart": {},
    })
    cart = CartService(repository)
    cart.add_item(conversation_id, "prod_001", 1)
    orders = OrderService(repository)
    orders.prepare_checkout(
        conversation_id,
        customer_name="Anu Thomas",
        email="anu@example.com",
        phone="+91 98765 43210",
        shipping_address="12 Lotus Avenue, Bengaluru, Karnataka 560001",
        turn_id="prepare-turn",
    )
    repository.update_conversation(conversation_id, {
        "pending_checkout": {
            **repository.get_conversation(conversation_id)["pending_checkout"],
            "summary_presented": True,
        }
    })
    cart.update_item(conversation_id, "prod_001", 2)

    with pytest.raises(ConflictError, match="cart changed"):
        orders.place_prepared_order(conversation_id, turn_id="confirm-turn", confirmed=True)
    assert repository.get_order_by_customer(repository.demo_customer_id) == []


@pytest.mark.parametrize(
    ("payment_outcome", "expected_status"),
    [("failed", "failed"), ("paid", "paid")],
)
def test_chat_verifies_payment_and_returns_verified_result(payment_outcome, expected_status):
    repository = MemoryRepository()
    conversation_id = "conv_payment_verification_test"
    repository.create_conversation({
        "conversation_id": conversation_id,
        "customer_id": repository.demo_customer_id,
        "messages": [],
        "cart": {},
    })
    CartService(repository).add_item(conversation_id, "prod_001", 1)
    order_service = OrderService(repository)
    order = order_service.create_order(
        conversation_id,
        shipping_address="12 Lotus Avenue, Bengaluru, Karnataka 560001",
        customer_id=repository.demo_customer_id,
        confirmed=True,
        customer_name="Anu Thomas",
        email="anu@example.com",
        phone="+91 98765 43210",
    )
    order_service.simulate_payment_outcome(order["id"], payment_outcome)

    class VerifyPaymentProvider:
        def __init__(self):
            self.calls = 0

        def generate_response(self, messages, tools=None):
            self.calls += 1
            if self.calls == 1:
                return AIResponse(content="", tool_calls=[ToolCall(
                    name="verify_latest_payment",
                    arguments={"order_id": order["id"]},
                )])
            return AIResponse(content="I checked the payment.")

    response = ChatService(
        repository=repository,
        llm_provider=VerifyPaymentProvider(),
    ).handle_message(conversation_id, "I've paid")

    assert response["order"]["id"] == order["id"]
    assert response["order"]["payment_status"] == expected_status
    if expected_status == "failed":
        assert "Payment failed" in response["response"]
        assert order["payment_url"] in response["response"]
        assert "try again" in response["response"]
    else:
        assert order["id"] in response["response"]
        assert "prod_001" not in response["response"]
        assert repository.get_product("prod_001")["name"] in response["response"]
        assert str(order["total"]) in response["response"]


@pytest.mark.parametrize("message", ["yes", "Yes, place the order.", "seri", "ശരി", "theek hai", "हाँ"])
def test_order_confirmation_recognizes_supported_confirmation_phrases(message):
    from app.ai.tool_registry import ToolExecutor

    assert ToolExecutor._explicitly_confirmed(message)


@pytest.mark.parametrize("message", ["yes, but change the address", "not yet", "maybe later"])
def test_order_confirmation_does_not_accept_ambiguous_messages(message):
    from app.ai.tool_registry import ToolExecutor

    assert not ToolExecutor._explicitly_confirmed(message)


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
