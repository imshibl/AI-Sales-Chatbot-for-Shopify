from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from app.core.exceptions import AppError
from app.repositories.memory import MemoryRepository
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
    max_price: int | None = Field(default=None, ge=0)


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


TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "search_products",
        "description": "Search the live Thai Naturals demo catalog. Returns only real catalog products.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search words for product name, ingredients, or description."},
                "category": {"type": "STRING", "description": "Product category such as cleanser, serum, toner, moisturizer, sunscreen, or face mask."},
                "skin_type": {"type": "STRING", "description": "Skin type filter such as oily, dry, combination, sensitive, or normal."},
                "concern": {"type": "STRING", "description": "Catalog concern filter, such as dryness, dullness, oiliness, or acne marks."},
                "max_price": {"type": "INTEGER", "description": "Maximum price in INR."},
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
                "max_price": {"type": "INTEGER", "description": "Maximum price in INR."},
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
]


class ToolExecutor:
    def __init__(self, repository: MemoryRepository, conversation_id: str, customer_id: str) -> None:
        self.repository = repository
        self.conversation_id = conversation_id
        self.customer_id = customer_id
        self.products = ProductService(repository)
        self.recommendations = RecommendationService(repository)
        self.cart = CartService(repository)
        self.orders = OrderService(repository)

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
                return {
                    "order": self.orders.get_order(
                        values["order_id"],
                        customer_id=self.customer_id,
                    )
                }
            if name == "get_payment_link":
                order = self.orders.get_order(
                    values["order_id"],
                    customer_id=self.customer_id,
                )
                return {
                    "payment_url": order.get("payment_url"),
                    "payment_status": order.get("payment_status"),
                }
            if name == "get_tracking_information":
                return {
                    "tracking": self.orders.get_tracking_information(
                        values["order_id"],
                        customer_id=self.customer_id,
                    )
                }
        except PydanticValidationError:
            return {"error": "The requested action had invalid arguments. Please ask the customer to clarify."}
        except AppError as exc:
            return {"error": exc.message}

        return {"error": "That action is not available."}
