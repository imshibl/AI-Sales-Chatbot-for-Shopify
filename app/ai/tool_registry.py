from __future__ import annotations

from typing import Any

import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError, field_validator

from app.core.config import settings
from app.core.exceptions import AppError
from app.repositories.interfaces import BaseRepository
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.recommendation_service import RecommendationService


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArguments(ToolArguments):
    pass


class ProductSearchArguments(ToolArguments):
    query: str | None = None
    category: str | None = None
    skin_type: str | None = None
    concern: str | None = None
    max_price: float | None = Field(default=None, ge=0)


class ProductDetailsArguments(ToolArguments):
    product_id: str = Field(min_length=1)


class ProductCompareArguments(ToolArguments):
    product_ids: list[str] = Field(min_length=2, max_length=2)


class CartProductArguments(ToolArguments):
    product_id: str = Field(min_length=1)


class CartQuantityArguments(CartProductArguments):
    quantity: int = Field(ge=1)


class OrderArguments(ToolArguments):
    order_id: str = Field(min_length=1)


class PaymentVerificationArguments(ToolArguments):
    order_id: str | None = Field(default=None, min_length=1)


class CheckoutArguments(ToolArguments):
    customer_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=7, max_length=32)
    shipping_address: str = Field(min_length=10, max_length=500)

    @field_validator("customer_name", "email", "phone", "shipping_address")
    @classmethod
    def strip_contact_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not re.fullmatch(r"[+()\d.\-\s]{7,32}", value) or len(re.sub(r"\D", "", value)) < 7:
            raise ValueError("Enter a valid phone number.")
        return value


TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "search_products",
        "description": "Search the connected store catalog. Returns only real catalog products.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search words for product name, ingredients, or description."},
                "category": {"type": "STRING", "description": "Product category such as cleanser, serum, toner, moisturizer, sunscreen, or face mask."},
                "skin_type": {"type": "STRING", "description": "Skin type filter such as oily, dry, combination, sensitive, or normal."},
                "concern": {"type": "STRING", "description": "Catalog concern filter, such as dryness, dullness, oiliness, or acne marks."},
                "max_price": {"type": "NUMBER", "description": f"Maximum price in {settings.currency}."},
            },
        },
    },
    {
        "name": "get_product_recommendations",
        "description": "Get deterministic product recommendations based on catalog data and the customer's stated needs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Relevant product search terms or ingredients."},
                "category": {"type": "STRING", "description": "Optional product category."},
                "skin_type": {"type": "STRING", "description": "The customer's stated skin type."},
                "concern": {"type": "STRING", "description": "A concern represented in catalog data."},
                "max_price": {"type": "NUMBER", "description": f"Maximum price in {settings.currency}."},
            },
        },
    },
    {
        "name": "get_product_details",
        "description": "Get full verified details for a catalog product by its ID.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"product_id": {"type": "STRING", "description": "Catalog product ID."}},
            "required": ["product_id"],
        },
    },
    {
        "name": "compare_products",
        "description": "Compare two real catalog products by their IDs, including actual prices and verified product details.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_ids": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "Exactly two catalog product IDs.",
                }
            },
            "required": ["product_ids"],
        },
    },
    {
        "name": "get_cart",
        "description": "Get the current conversation's cart. Do not request or provide a conversation ID.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "add_to_cart",
        "description": "Add an available catalog item to this conversation's cart.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_id": {"type": "STRING", "description": "Catalog product ID."},
                "quantity": {"type": "INTEGER", "description": "Number of units to add."},
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "update_cart_item",
        "description": "Set the quantity for a product already in the cart.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "product_id": {"type": "STRING", "description": "Catalog product ID."},
                "quantity": {"type": "INTEGER", "description": "New quantity; must be at least one."},
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "remove_from_cart",
        "description": "Remove a product from this conversation's cart.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"product_id": {"type": "STRING", "description": "Catalog product ID."}},
            "required": ["product_id"],
        },
    },
    {
        "name": "calculate_cart_total",
        "description": "Calculate the current cart subtotal, shipping fee, and total using backend prices.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_shipping_policy",
        "description": "Get the configured demo shipping policy.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_order_status",
        "description": "Get an order's status only for the current demo customer. Ask for the order ID if it is not known.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"order_id": {"type": "STRING", "description": "Customer's order ID."}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_payment_link",
        "description": "Retrieve the existing demo payment link and status for an order belonging to the current demo customer.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"order_id": {"type": "STRING", "description": "Customer's order ID."}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_tracking_information",
        "description": "Get configured demo tracking details for an order belonging to the current demo customer.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"order_id": {"type": "STRING", "description": "Customer's order ID."}},
            "required": ["order_id"],
        },
    },
    {
        "name": "prepare_order",
        "description": (
            "Prepare checkout after the customer asks to order and has provided their full name, email, "
            "phone number, and delivery address. Returns the verified cart items and backend-calculated total. "
            "This does not create an order or payment link. Present the exact summary and ask for explicit "
            "confirmation; wait for the customer's next message before calling place_order."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "customer_name": {"type": "STRING", "description": "Recipient's full name."},
                "email": {"type": "STRING", "description": "Customer's email address."},
                "phone": {"type": "STRING", "description": "Customer's contact phone number."},
                "shipping_address": {"type": "STRING", "description": "Complete delivery address including postal code."},
            },
            "required": ["customer_name", "email", "phone", "shipping_address"],
        },
    },
    {
        "name": "place_order",
        "description": (
            "Create the prepared order and demo payment link only after the customer explicitly confirms "
            "the exact order summary in a later message. This creates an order with pending payment; never "
            "claim payment succeeded. Returns the verified order ID, total, and payment URL."
        ),
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "list_my_orders",
        "description": "List active orders and full order history for the current demo customer, including payment and order statuses.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "verify_latest_payment",
        "description": (
            "Verify an order's payment directly with the payment provider after the customer says they paid. "
            "Provide order_id when the customer identifies a specific order; otherwise verify their latest order. "
            "Returns current payment and order status, order ID, order items, total, and payment link if payment "
            "failed or remains pending. Never infer success from the customer's message."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {"order_id": {"type": "STRING", "description": "Optional order ID mentioned by the customer."}},
        },
    },
]


class ToolExecutor:
    def __init__(
        self,
        repository: BaseRepository,
        conversation_id: str,
        customer_id: str,
        current_user_message: str = "",
        turn_id: str = "",
    ) -> None:
        self.repository = repository
        self.conversation_id = conversation_id
        self.customer_id = customer_id
        self.current_user_message = current_user_message
        self.turn_id = turn_id
        self.products = ProductService(repository)
        self.recommendations = RecommendationService(repository)
        self.cart = CartService(repository)
        self.orders = OrderService(repository)

    @staticmethod
    def _explicitly_confirmed(message: str) -> bool:
        normalized = re.sub(r"[\s.!?,;:]+", " ", message.lower()).strip()
        confirmations = {
            "yes", "yes please", "yes i confirm", "yes confirm", "yes place the order",
            "yes place my order", "yes go ahead", "yes go ahead and place the order",
            "yes proceed", "confirm", "confirm it", "confirm order", "confirm the order",
            "place order", "place the order", "proceed", "proceed with the order",
            "proceed with checkout", "go ahead", "go ahead with the order", "i confirm",
            "okay", "ok", "okay do it", "sure", "sure go ahead",
            "ஆம்", "ஆமாம்", "சரி", "ஆர்டர் செய்யுங்கள்", "உறுதி செய்யுங்கள்",
            "ஆம் ஆர்டர் செய்யுங்கள்", "சரி ஆர்டர் செய்யுங்கள்",
            "aama", "aamam", "seri", "aama order pannunga", "confirm pannunga", "order pannunga",
            "അതെ", "ശരി", "ഓർഡർ ചെയ്യൂ", "ഓർഡർ ഉറപ്പിക്കൂ", "ശരി ഓർഡർ ചെയ്യൂ",
            "athe", "sheri", "sheri order cheyyam", "cheytholu", "order confirm cheyyu",
            "हाँ", "हां", "ठीक है", "ऑर्डर पक्का करें", "हाँ ऑर्डर करें",
            "haan", "han", "theek hai", "haan order kar do", "order pakka karo", "confirm karo",
        }
        return normalized in confirmations

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        validators = {
            "search_products": ProductSearchArguments,
            "get_product_recommendations": ProductSearchArguments,
            "get_product_details": ProductDetailsArguments,
            "compare_products": ProductCompareArguments,
            "add_to_cart": CartQuantityArguments,
            "update_cart_item": CartQuantityArguments,
            "remove_from_cart": CartProductArguments,
            "get_order_status": OrderArguments,
            "get_tracking_information": OrderArguments,
            "get_payment_link": OrderArguments,
            "prepare_order": CheckoutArguments,
            "place_order": EmptyArguments,
            "list_my_orders": EmptyArguments,
            "verify_latest_payment": PaymentVerificationArguments,
            "get_cart": EmptyArguments,
            "calculate_cart_total": EmptyArguments,
            "get_shipping_policy": EmptyArguments,
        }
        validator = validators.get(name)
        if name not in {tool["name"] for tool in TOOL_DECLARATIONS}:
            return {"error": "That action is not available."}

        try:
            parsed = validator.model_validate(arguments or {}) if validator else None
            values = parsed.model_dump(exclude_none=True) if parsed else {}

            if name == "search_products":
                return {"products": self.products.search_products(**values)}
            if name == "get_product_recommendations":
                recommendation_arguments = dict(values)
                recommendation_arguments["budget"] = recommendation_arguments.pop("max_price", None)
                return {
                    "recommendations": self.recommendations.get_recommendations(
                        **recommendation_arguments,
                        limit=3,
                    )
                }
            if name == "get_product_details":
                return {"product": self.products.get_product(values["product_id"])}
            if name == "compare_products":
                return {
                    "products": [
                        self.products.get_product(product_id)
                        for product_id in values["product_ids"]
                    ]
                }
            if name == "get_cart":
                return {"cart": self.cart.get_cart(self.conversation_id)}
            if name == "add_to_cart":
                return {"cart": self.cart.add_item(self.conversation_id, values["product_id"], values["quantity"])}
            if name == "update_cart_item":
                return {"cart": self.cart.update_item(self.conversation_id, values["product_id"], values["quantity"])}
            if name == "remove_from_cart":
                return {"cart": self.cart.remove_item(self.conversation_id, values["product_id"])}
            if name == "calculate_cart_total":
                return {
                    "total": self.cart.calculate_total(
                        self.conversation_id,
                        shipping_fee=self.repository.store_policies.get("shipping", {}).get("shipping_fee", 50),
                    )
                }
            if name == "get_shipping_policy":
                return {"shipping_policy": self.products.get_shipping_policy()}
            if name == "get_order_status":
                order = self.orders.refresh_payment_status(
                    values["order_id"],
                    customer_id=self.customer_id,
                )
                return {
                    "order": self._public_order_status(order)
                }
            if name == "get_payment_link":
                order = self.orders.refresh_payment_status(
                    values["order_id"],
                    customer_id=self.customer_id,
                )
                return {
                    "payment_url": order.get("payment_url"),
                    "payment_status": order.get("payment_status"),
                }
            if name == "list_my_orders":
                listed = self.orders.list_customer_orders(self.customer_id)
                return {
                    "active_orders": [self._public_order_status(order) for order in listed["active_orders"]],
                    "order_history": [self._public_order_status(order) for order in listed["order_history"]],
                }
            if name == "verify_latest_payment":
                if values.get("order_id"):
                    latest = self.orders.refresh_payment_status(
                        values["order_id"],
                        customer_id=self.customer_id,
                    )
                else:
                    listed = self.orders.list_customer_orders(self.customer_id)
                    if not listed["order_history"]:
                        return {"error": "There are no orders to verify yet."}
                    latest = listed["order_history"][0]
                return {
                    "order": self._public_order_status(latest)
                }
            if name == "get_tracking_information":
                return {
                    "tracking": self.orders.get_tracking_information(
                        values["order_id"],
                        customer_id=self.customer_id,
                    )
                }
            if name == "prepare_order":
                return {
                    "checkout": self.orders.prepare_checkout(
                        self.conversation_id,
                        turn_id=self.turn_id,
                        **values,
                    )
                }
            if name == "place_order":
                order = self.orders.place_prepared_order(
                    self.conversation_id,
                    turn_id=self.turn_id,
                    confirmed=self._explicitly_confirmed(self.current_user_message),
                    customer_id=self.customer_id,
                )
                return {
                    "order": {
                        "id": order["id"],
                        "total": order["total"],
                        "currency": order["currency"],
                        "payment_status": order["payment_status"],
                        "order_status": order["order_status"],
                        "payment_url": order["payment_url"],
                    }
                }
        except PydanticValidationError:
            return {"error": "The requested action had invalid arguments. Please ask the customer to clarify."}
        except AppError as exc:
            return {"error": exc.message}

        return {"error": "That action is not available."}

    @staticmethod
    def _public_order_status(order: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": order["id"],
            "created_at": order.get("created_at"),
            "total": order.get("total"),
            "currency": order.get("currency"),
            "payment_status": order.get("payment_status"),
            "order_status": order.get("order_status"),
            "payment_url": order.get("payment_url"),
            "tracking_number": order.get("tracking_number"),
            "items": order.get("items", []),
        }
