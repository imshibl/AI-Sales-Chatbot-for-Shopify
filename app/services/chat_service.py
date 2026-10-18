from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.ai.factory import get_llm_provider
from app.ai.interfaces import LLMProvider
from app.ai.tool_registry import TOOL_DECLARATIONS, ToolExecutor
from app.core.config import settings
from app.core.exceptions import AIServiceError, NotFoundError, ValidationError
from app.repositories.memory import MemoryRepository, repository
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.recommendation_service import RecommendationService

repo = repository
product_service = ProductService(repo)
recommendation_service = RecommendationService(repo)
cart_service = CartService(repo)
order_service = OrderService(repo)


class ChatService:
    def __init__(self, repository: MemoryRepository | None = None, llm_provider: LLMProvider | None = None):
        self.repository = repository or repo
        self.product_service = ProductService(self.repository)
        self.recommendation_service = RecommendationService(self.repository)
        self.cart_service = CartService(self.repository)
        self.order_service = OrderService(self.repository)
        self.use_llm = llm_provider is not None or settings.llm_provider.lower() == "gemini"
        self.llm_provider = llm_provider or get_llm_provider()

    def _get_or_create_conversation(self, conversation_id: str | None, customer_id: str | None = None) -> dict:
        if conversation_id and self.repository.get_conversation(conversation_id):
            return self.repository.get_conversation(conversation_id)
        new_id = conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        payload = {
            "conversation_id": new_id,
            "customer_id": customer_id or self.repository.demo_customer_id,
            "messages": [],
            "cart": {},
        }
        return self.repository.create_conversation(payload)

    def _parse_max_price(self, text: str) -> int | None:
        match = re.search(r"under\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)|under\s*rs\s*(\d+(?:,\d{3})*(?:\.\d+)?)|budget\s*(\d+)", text.lower())
        if not match:
            return None
        value = next(group for group in match.groups() if group)
        value = value.replace(",", "")
        return int(float(value))

    def _find_product_by_text(self, text: str) -> dict | None:
        needle = text.lower().strip()
        if not needle:
            return None
        for product in self.repository.list_products():
            haystack = f"{product['name']} {product['slug']} {product['category']} {' '.join(product.get('benefits', []))}".lower()
            if needle in haystack:
                return product
        return None

    def _llm_history(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for message in history[-settings.chat_history_limit :]:
            role = message.get("role")
            if role == "user":
                messages.append({"role": "user", "content": message.get("content", "")})
                continue
            if role != "assistant":
                continue
            for step in message.get("tool_steps", []):
                messages.append(
                    {
                        "role": "assistant",
                        "content": step.get("content", ""),
                        "tool_calls": step.get("tool_calls", []),
                    }
                )
                for result in step.get("results", []):
                    messages.append(
                        {
                            "role": "tool",
                            "name": result["name"],
                            "call_id": result.get("call_id", ""),
                            "content": result.get("content", "{}"),
                        }
                    )
            messages.append({"role": "assistant", "content": message.get("content", "")})
        return messages

    def _handle_with_llm(
        self,
        conversation: dict[str, Any],
        user_message: str,
        history: list[dict[str, Any]],
        language: str,
    ) -> dict[str, Any]:
        conversation_id = conversation["conversation_id"]
        customer_id = conversation.get("customer_id") or self.repository.demo_customer_id
        turn_id = uuid.uuid4().hex
        executor = ToolExecutor(
            self.repository,
            conversation_id,
            customer_id,
            current_user_message=user_message,
            turn_id=turn_id,
        )
        messages = self._llm_history(history)
        language_names = {
            "en": "English",
            "ta": "Tamil",
            "ml": "Malayalam",
            "hi": "Hindi",
        }
        messages.append(
            {
                "role": "system",
                "content": (
                    f"The customer's selected language preference is {language_names[language]}. "
                    "Use it as a fallback for a new or ambiguous conversation, but do not let it override "
                    "the language and writing style the customer actually uses or explicitly requests. "
                    "Detect language from the message and recent conversation, including code-switching "
                    "and regional transliterations written in Latin letters: Manglish (Malayalam), "
                    "Tanglish (Tamil), and Hinglish (Hindi). Understand English skincare terms mixed into "
                    "those languages. Reply naturally in the customer's language or mix of languages, "
                    "and match their script: use Latin transliteration when they write the regional language "
                    "in Latin letters, and native script when they use native script. For mixed-language "
                    "messages, mirror their natural balance instead of translating everything into one language. "
                    "Use recent conversation turns to keep their language and script consistent; honor an "
                    "explicit request to switch language. "
                    "Keep product names, ingredient names, and currency amounts accurate."
                ),
            }
        )
        tool_steps: list[dict[str, Any]] = []
        products_by_id: dict[str, dict[str, Any]] = {}
        tracking: dict[str, Any] | None = None
        response_text = ""
        cart_mutated = False
        created_order: dict[str, Any] | None = None
        verified_order: dict[str, Any] | None = None
        checkout_prepared = False
        assistant_finalized = False

        for round_index in range(5):
            try:
                response = self.llm_provider.generate_response(messages, tools=TOOL_DECLARATIONS)
            except AIServiceError:
                if not cart_mutated and not created_order and not verified_order:
                    raise
                if created_order:
                    response_text = (
                        f"Your order {created_order['id']} is ready with payment pending. "
                        f"Complete demo payment here: {created_order['payment_url']}"
                    )
                elif verified_order:
                    response_text = "I checked the payment provider status for your order."
                else:
                    response_text = (
                        "Your cart was updated successfully. The AI response is temporarily unavailable, "
                        "so please review your cart before checking out."
                    )
                break
            response_text = response.content.strip()
            if not response.tool_calls:
                assistant_finalized = True
                break
            if round_index == 4:
                if created_order:
                    response_text = (
                        f"Your order {created_order['id']} is ready with payment pending. "
                        f"Complete demo payment here: {created_order['payment_url']}"
                    )
                elif verified_order:
                    response_text = "I checked the payment provider status for your order."
                else:
                    response_text = (
                        "Your cart was updated successfully. Please review it before checking out."
                        if cart_mutated
                        else "I couldn't complete that request just now. Please try again, or use the catalog, cart, and checkout controls."
                    )
                break

            calls = [
                {
                    "name": call.name,
                    "arguments": call.arguments,
                    "call_id": call.call_id or str(uuid.uuid4()),
                    "thought_signature": call.thought_signature,
                }
                for call in response.tool_calls
            ]
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": calls,
                }
            )
            results = []
            for call in calls:
                result = executor.execute(call["name"], call["arguments"])
                if call["name"] in {"add_to_cart", "update_cart_item", "remove_from_cart"} and "error" not in result:
                    cart_mutated = True
                if call["name"] == "place_order" and "order" in result:
                    created_order = result["order"]
                if call["name"] == "verify_latest_payment" and "order" in result:
                    verified_order = result["order"]
                if call["name"] == "prepare_order" and "checkout" in result:
                    checkout_prepared = True
                result_text = json.dumps(result, ensure_ascii=False)
                results.append(
                    {
                        "name": call["name"],
                        "call_id": call["call_id"],
                        "content": result_text,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "name": call["name"],
                        "call_id": call["call_id"],
                        "content": result_text,
                    }
                )
                self._collect_tool_result(call["name"], result, products_by_id)
                if call["name"] == "get_tracking_information":
                    tracking = result.get("tracking")
            tool_steps.append(
                {
                    "content": response.content,
                    "tool_calls": calls,
                    "results": results,
                }
            )
        else:
            raise AIServiceError("I couldn't prepare a response just now. Please try again.")

        if created_order and created_order["payment_url"] not in response_text:
            response_text = (
                f"{response_text}\n\nOrder {created_order['id']} is awaiting payment. "
                f"Complete demo payment here: {created_order['payment_url']}"
            )
        if verified_order:
            status = verified_order.get("payment_status")
            if status == "paid":
                items = ", ".join(
                    f"{item['product_name']} × {item['quantity']}"
                    for item in verified_order.get("items", [])
                )
                verification = (
                    f"Verified order {verified_order['id']}: {items}; "
                    f"total {verified_order['currency']} {verified_order['total']}; "
                    f"order status {verified_order['order_status']}."
                )
                if (
                    verified_order["id"] not in response_text
                    or str(verified_order["total"]) not in response_text
                    or any(item["product_name"] not in response_text for item in verified_order.get("items", []))
                ):
                    response_text = f"{response_text}\n\n{verification}"
            elif status in {"failed", "cancelled"}:
                if (
                    verified_order["payment_url"] not in response_text
                    or not any(phrase in response_text.lower() for phrase in ("try again", "retry"))
                ):
                    response_text = (
                        f"{response_text}\n\nPayment failed for order {verified_order['id']}. "
                        f"Please try again using this demo payment link: {verified_order['payment_url']}"
                    )
            elif status == "pending":
                if verified_order["payment_url"] not in response_text:
                    response_text = (
                        f"{response_text}\n\nPayment for order {verified_order['id']} is not verified yet. "
                        f"Please complete payment here: {verified_order['payment_url']}"
                    )
        if not response_text:
            raise AIServiceError("I couldn't prepare a response just now. Please try again.")

        product_cards = [self._product_card(product) for product in products_by_id.values()]
        cart_summary = self.cart_service.get_cart(conversation_id)
        from datetime import datetime, timezone

        history.append(
            {
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_steps": tool_steps,
                "order": created_order or verified_order,
            }
        )
        conversation_update: dict[str, Any] = {"messages": history, "cart": cart_summary}
        current_conversation = self.repository.get_conversation(conversation_id)
        pending_checkout = current_conversation.get("pending_checkout") if current_conversation else None
        if (
            checkout_prepared
            and assistant_finalized
            and pending_checkout
            and pending_checkout.get("prepared_turn_id") == turn_id
        ):
            conversation_update["pending_checkout"] = {
                **pending_checkout,
                "summary_presented": True,
            }
        self.repository.update_conversation(conversation_id, conversation_update)
        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "product_cards": product_cards,
            "cart": cart_summary,
            "order_summary": created_order,
            "payment_link": created_order.get("payment_url") if created_order else None,
            "order": created_order or verified_order,
            "tracking": tracking,
        }

    @staticmethod
    def _collect_tool_result(
        tool_name: str,
        result: dict[str, Any],
        products_by_id: dict[str, dict[str, Any]],
    ) -> None:
        if "error" in result:
            return
        if tool_name in {"search_products", "get_product_recommendations"}:
            products = result.get("products") or result.get("recommendations") or []
            for product in products:
                if product.get("id"):
                    products_by_id[product["id"]] = product
        elif tool_name == "get_product_details":
            product = result.get("product")
            if product and product.get("id"):
                products_by_id[product["id"]] = product
        elif tool_name == "compare_products":
            for product in result.get("products", []):
                if product and product.get("id"):
                    products_by_id[product["id"]] = product

    @staticmethod
    def _product_card(product: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "description": product["description"],
            "benefits": product.get("benefits", []),
            "image_url": product.get("image_url"),
            "availability": "in stock" if product.get("stock_quantity", 0) > 0 else "out of stock",
            "category": product.get("category"),
        }

    def handle_message(
        self,
        conversation_id: str | None,
        user_message: str,
        customer_id: str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        if not user_message or not user_message.strip():
            raise ValidationError("Message cannot be empty.")
        if language not in {"en", "ta", "ml", "hi"}:
            raise ValidationError("Language must be one of en, ta, ml, or hi.")

        conversation = self._get_or_create_conversation(conversation_id, customer_id)
        from datetime import datetime, timezone

        history = conversation.get("messages", [])
        history.append({"role": "user", "content": user_message, "timestamp": datetime.now(timezone.utc).isoformat()})

        if self.use_llm:
            return self._handle_with_llm(conversation, user_message, history, language)

        lower = user_message.lower()
        response_text = "I'm here to help you with your skincare routine."
        product_cards: list[dict] = []
        cart_summary: dict | None = None
        order_summary: dict | None = None
        payment_link: str | None = None

        if lower.startswith("hi") or lower.startswith("hello") or lower.startswith("hey"):
            response_text = "Hi there! 👋 Welcome to Thai Naturals. I can help you find skincare that fits your skin and routine. What are you looking to improve today?"
        elif "add" in lower and "cart" in lower:
            product = self._find_product_by_text(lower.replace("add", "").replace("to my cart", "").strip())
            if not product:
                product = self.product_service.search_products(query=lower.replace("cart", ""), limit=False)[0] if self.product_service.search_products(query=lower.replace("cart", ""), limit=False) else None
            if product:
                cart_summary = self.cart_service.add_item(conversation["conversation_id"], product["id"], quantity=1)
                response_text = f"Absolutely! I've added {product['name']} to your cart. Would you like to review it or keep shopping?"
            else:
                response_text = "I couldn't find that product in the Thai Naturals catalog. Tell me the product name or what skin concern you want to target."
        elif "remove" in lower and "cart" in lower:
            product = self._find_product_by_text(lower.replace("remove", "").replace("from cart", "").strip())
            if product:
                cart_summary = self.cart_service.remove_item(conversation["conversation_id"], product["id"])
                response_text = f"I removed {product['name']} from your cart."
            else:
                response_text = "I couldn't find that product in your cart."
        elif any(phrase in lower for phrase in ("place the order", "checkout", "place order", "confirm order")):
            response_text = (
                "Conversational checkout requires the Gemini AI provider. Set LLM_PROVIDER=gemini "
                "with a valid API key and model to collect delivery details and place an order safely. "
                "This offline mode will not create an order."
            )
        elif "order history" in lower or "my orders" in lower or lower.strip() == "orders":
            order_list = self.order_service.list_customer_orders(self.repository.demo_customer_id)
            if order_list["order_history"]:
                response_text = "Your orders: " + "; ".join(
                    f"{order['id']} — {order['order_status']} (payment {order['payment_status']})"
                    for order in order_list["order_history"]
                )
            else:
                response_text = "You don't have any orders yet."
        elif "where is my order" in lower or "tracking" in lower or "status" in lower:
            order_id_match = re.search(r"TN-[A-Z0-9-]+", user_message.upper())
            order_id = order_id_match.group(0) if order_id_match else None
            if not order_id:
                orders = self.repository.get_order_by_customer(self.repository.demo_customer_id)
                if orders:
                    order = orders[-1]
                    order_id = order["id"]
            if order_id:
                self.order_service.refresh_payment_status(order_id, customer_id=self.repository.demo_customer_id)
                tracking = self.order_service.get_tracking_information(order_id, customer_id=self.repository.demo_customer_id)
                response_text = f"Your latest order {order_id} is currently {tracking['status']} and you can track it here: {tracking['tracking_url']}"
            else:
                response_text = "I can help you check that. Please share your order ID so I can look it up."
        else:
            max_price = self._parse_max_price(lower)
            skin_types = ("combination", "sensitive", "normal", "oily", "dry")
            skin_type = next((item for item in skin_types if re.search(rf"\b{item}\b", lower)), None)
            catalog_concerns = sorted(
                {concern for item in self.repository.list_products() for concern in item.get("concerns", [])},
                key=len,
                reverse=True,
            )
            concern = next((item for item in catalog_concerns if item.lower() in lower), None)
            categories = sorted(
                {item.get("category", "") for item in self.repository.list_products()},
                key=len,
                reverse=True,
            )
            category = next((item for item in categories if item and item.lower() in lower), None)
            mentioned_product = next(
                (item for item in self.repository.list_products() if item["name"].lower() in lower),
                None,
            )
            mentioned_ingredient = next(
                (
                    ingredient
                    for item in self.repository.list_products()
                    for ingredient in item.get("ingredients", [])
                    if ingredient.lower() in lower
                ),
                None,
            )
            query = mentioned_product["name"] if mentioned_product else mentioned_ingredient
            has_catalog_intent = any((skin_type, concern, category, query, max_price))
            results = self.recommendation_service.get_recommendations(
                query=query,
                budget=max_price,
                skin_type=skin_type,
                concern=concern,
                category=category,
                limit=3,
            ) if has_catalog_intent else []
            if not results:
                results = self.product_service.search_products(query=query or None, max_price=max_price)
            product_cards = [
                {
                    "id": product["id"],
                    "name": product["name"],
                    "price": product["price"],
                    "description": product["description"],
                    "benefits": product.get("benefits", []),
                    "image_url": product.get("image_url"),
                    "availability": "in stock" if product.get("stock_quantity", 0) > 0 else "out of stock",
                    "category": product.get("category"),
                }
                for product in results[:3]
            ]
            if results:
                product_names = ", ".join(item["name"] for item in results[:3])
                response_text = f"Here are a few Thai Naturals products that match your request: {product_names}. I can help narrow this down further based on your skin type, routine, or budget."
            else:
                response_text = "I couldn't find a clear match in the catalog. Tell me your skin type, concern, or budget and I can suggest a few options."

        cart_summary = cart_summary or self.cart_service.get_cart(conversation["conversation_id"])
        history.append({"role": "assistant", "content": response_text, "timestamp": datetime.now(timezone.utc).isoformat()})
        conversation["messages"] = history
        self.repository.update_conversation(conversation["conversation_id"], {"messages": history, "cart": cart_summary or conversation.get("cart", {})})

        return {
            "response": response_text,
            "conversation_id": conversation["conversation_id"],
            "product_cards": product_cards,
            "cart": cart_summary or {},
            "order_summary": order_summary,
            "payment_link": payment_link,
            "tracking": None,
        }
