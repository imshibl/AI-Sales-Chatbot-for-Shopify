from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.data.seed import sample_products, sample_store_policies
from app.repositories.interfaces import BaseRepository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryRepository(BaseRepository):
    def __init__(self) -> None:
        self.products: dict[str, dict[str, Any]] = {product["id"]: product for product in sample_products()}
        self.customers: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        self.store_policies = sample_store_policies()
        self._demo_customer = {
            "id": "customer_demo_001",
            "name": "Demo Customer",
            "email": "demo@thainaturals.ai",
            "phone": "+91 98765 43210",
            "shipping_address": "12 Lotus Avenue, Bengaluru, Karnataka 560001",
            "created_at": utcnow().isoformat(),
        }
        self.customers[self._demo_customer["id"]] = self._demo_customer

    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        items = list(self.products.values())
        if active_only:
            items = [p for p in items if p.get("is_active")]
        return [dict(p) for p in items]

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        product = self.products.get(product_id)
        return dict(product) if product else None

    def search_products(
        self,
        *,
        query: str | None = None,
        category: str | None = None,
        skin_type: str | None = None,
        concern: str | None = None,
        max_price: float | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        results = list(self.products.values())
        q = (query or "").lower()
        if active_only:
            results = [p for p in results if p.get("is_active")]
        if category:
            results = [p for p in results if p.get("category", "").lower() == category.lower()]
        if skin_type:
            results = [p for p in results if skin_type.lower() in [x.lower() for x in p.get("skin_types", [])]]
        if concern:
            results = [p for p in results if concern.lower() in [x.lower() for x in p.get("concerns", [])]]
        if max_price is not None:
            results = [p for p in results if float(p.get("price", 0)) <= max_price]
        if q:
            results = [
                p
                for p in results
                if q in p.get("name", "").lower()
                or q in p.get("category", "").lower()
                or q in p.get("description", "").lower()
                or any(q in item.lower() for item in p.get("ingredients", []))
                or any(q in tag.lower() for tag in p.get("benefits", []))
                or any(q in tag.lower() for tag in p.get("concerns", []))
                or any(q in tag.lower() for tag in p.get("skin_types", []))
            ]
        return [dict(p) for p in results]

    def create_customer(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer_id = payload.get("id") or str(uuid.uuid4())
        customer = {
            "id": customer_id,
            "name": payload.get("name", "Customer"),
            "email": payload.get("email", f"customer-{customer_id}@example.com"),
            "phone": payload.get("phone", ""),
            "shipping_address": payload.get("shipping_address", ""),
            "created_at": utcnow().isoformat(),
        }
        self.customers[customer_id] = customer
        return dict(customer)

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        customer = self.customers.get(customer_id)
        return dict(customer) if customer else None

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            return None
        return dict(conversation)

    def create_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        conversation_id = payload.get("conversation_id") or str(uuid.uuid4())
        conversation = {
            "conversation_id": conversation_id,
            "customer_id": payload.get("customer_id"),
            "messages": payload.get("messages", []),
            "cart": payload.get("cart", {}),
            "created_at": payload.get("created_at") or utcnow().isoformat(),
            "updated_at": payload.get("updated_at") or utcnow().isoformat(),
        }
        self.conversations[conversation_id] = conversation
        return dict(conversation)

    def update_conversation(self, conversation_id: str, updated: dict[str, Any]) -> dict[str, Any]:
        existing = self.conversations.get(conversation_id)
        if not existing:
            raise KeyError(f"Unknown conversation: {conversation_id}")
        existing.update(updated)
        existing["updated_at"] = utcnow().isoformat()
        self.conversations[conversation_id] = existing
        return dict(existing)

    def delete_conversation(self, conversation_id: str) -> None:
        self.conversations.pop(conversation_id, None)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        order_id = payload.get("id") or f"TN-{uuid.uuid4().hex[:8].upper()}"
        created = {
            "id": order_id,
            "customer_id": payload["customer_id"],
            "items": payload.get("items", []),
            "subtotal": payload.get("subtotal", 0),
            "shipping_fee": payload.get("shipping_fee", 0),
            "discount": payload.get("discount", 0),
            "total": payload.get("total", 0),
            "currency": payload.get("currency", "INR"),
            "payment_status": payload.get("payment_status", "pending"),
            "order_status": payload.get("order_status", "pending_payment"),
            "payment_url": payload.get("payment_url"),
            "tracking_url": payload.get("tracking_url"),
            "tracking_number": payload.get("tracking_number"),
            "shipping_address": payload.get("shipping_address", ""),
            "customer_name": payload.get("customer_name", ""),
            "email": payload.get("email", ""),
            "phone": payload.get("phone", ""),
            "created_at": payload.get("created_at") or utcnow().isoformat(),
            "updated_at": payload.get("updated_at") or utcnow().isoformat(),
        }
        self.orders[order_id] = created
        return dict(created)

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        order = self.orders.get(order_id)
        return dict(order) if order else None

    def get_order_by_payment_reference(self, payment_reference: str) -> dict[str, Any] | None:
        order = next(
            (item for item in self.orders.values() if item.get("payment_reference") == payment_reference),
            None,
        )
        return dict(order) if order else None

    def get_order_by_customer(self, customer_id: str) -> list[dict[str, Any]]:
        return [dict(order) for order in self.orders.values() if order.get("customer_id") == customer_id]

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            raise KeyError(f"Unknown order: {order_id}")
        order.update(payload)
        order["updated_at"] = utcnow().isoformat()
        self.orders[order_id] = order
        return dict(order)

    @property
    def demo_customer_id(self) -> str:
        return self._demo_customer["id"]
