"""SQLAlchemy-backed persistence for conversations, customers, and orders."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, MetaData, String, Table, create_engine, insert, select, update
from sqlalchemy.engine import Engine

from app.core.exceptions import NotFoundError
from app.data.seed import sample_products, sample_store_policies


def utcnow() -> str:
    """Serialize a timezone-aware timestamp for JSON storage."""
    return datetime.now(timezone.utc).isoformat()


class SQLAlchemyRepository:
    """Persist repository entities as JSON payloads in relational tables."""

    def __init__(self, database_url: str):
        if not database_url.strip():
            raise ValueError("DATABASE_URL is required when STORAGE_BACKEND=sql.")
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(database_url, connect_args=connect_args)
        # Keep application records in separate tables while allowing schema evolution.
        metadata = MetaData()
        self.products = self._entity_table(metadata, "products")
        self.customers = self._entity_table(metadata, "customers")
        self.conversations = self._entity_table(metadata, "conversations")
        self.orders = self._entity_table(metadata, "orders")
        metadata.create_all(self.engine)
        self.store_policies = sample_store_policies()
        self._demo_customer = {
            "id": "customer_demo_001",
            "name": "Demo Customer",
            "email": "demo@thainaturals.ai",
            "phone": "+91 98765 43210",
            "shipping_address": "12 Lotus Avenue, Bengaluru, Karnataka 560001",
            "created_at": utcnow(),
        }
        self._initialize_defaults()

    @staticmethod
    def _entity_table(metadata: MetaData, name: str) -> Table:
        return Table(
            name,
            metadata,
            Column("id", String, primary_key=True),
            Column("payload", JSON, nullable=False),
        )

    def _initialize_defaults(self) -> None:
        """Seed the demo catalog/customer only when their tables are empty."""
        with self.engine.begin() as connection:
            if connection.execute(select(self.products.c.id).limit(1)).first() is None:
                connection.execute(insert(self.products), [{"id": item["id"], "payload": item} for item in sample_products()])
            if connection.execute(select(self.customers.c.id).where(self.customers.c.id == self._demo_customer["id"])).first() is None:
                connection.execute(insert(self.customers).values(id=self._demo_customer["id"], payload=self._demo_customer))

    @staticmethod
    def _key(table: Table, payload: dict[str, Any]) -> str:
        """Use conversation_id for conversations and id for other entity tables."""
        key_name = "conversation_id" if table.name == "conversations" else "id"
        value = payload.get(key_name)
        if not value:
            raise ValueError(f"{table.name} payload requires '{key_name}'.")
        return str(value)

    def _get(self, table: Table, key: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            payload = connection.execute(
                select(table.c.payload).where(table.c.id == key)
            ).scalar_one_or_none()
        return dict(payload) if payload is not None else None

    def _all(self, table: Table) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(select(table.c.payload)).scalars().all()
        return [dict(row) for row in rows]

    def _save(self, table: Table, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert or replace one JSON entity inside a database transaction."""
        value = dict(payload)
        key = self._key(table, value)
        with self.engine.begin() as connection:
            exists = connection.execute(select(table.c.id).where(table.c.id == key)).first()
            if exists:
                connection.execute(update(table).where(table.c.id == key).values(payload=value))
            else:
                connection.execute(insert(table).values(id=key, payload=value))
        return value

    # Catalog operations preserve the same filtering semantics as MemoryRepository.
    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        products = self._all(self.products)
        return [product for product in products if not active_only or product.get("is_active")]

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        return self._get(self.products, product_id)

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
        results = self.list_products(active_only=active_only)
        needle = (query or "").lower()
        if category:
            results = [item for item in results if item.get("category", "").lower() == category.lower()]
        if skin_type:
            results = [item for item in results if skin_type.lower() in [value.lower() for value in item.get("skin_types", [])]]
        if concern:
            results = [item for item in results if concern.lower() in [value.lower() for value in item.get("concerns", [])]]
        if max_price is not None:
            results = [item for item in results if float(item.get("price", 0)) <= max_price]
        if needle:
            results = [
                item for item in results
                if needle in item.get("name", "").lower()
                or needle in item.get("category", "").lower()
                or needle in item.get("description", "").lower()
                or any(needle in value.lower() for value in item.get("ingredients", []))
                or any(needle in value.lower() for value in item.get("benefits", []))
                or any(needle in value.lower() for value in item.get("concerns", []))
                or any(needle in value.lower() for value in item.get("skin_types", []))
            ]
        return results

    # Customer and conversation operations implement the service-facing repository API.
    def create_customer(self, payload: dict[str, Any]) -> dict[str, Any]:
        customer_id = str(payload.get("id") or uuid.uuid4())
        customer = {
            "id": customer_id,
            "name": payload.get("name", "Customer"),
            "email": payload.get("email", f"customer-{customer_id}@example.com"),
            "phone": payload.get("phone", ""),
            "shipping_address": payload.get("shipping_address", ""),
            "created_at": utcnow(),
        }
        return self._save(self.customers, customer)

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        return self._get(self.customers, customer_id)

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        return self._get(self.conversations, conversation_id)

    def create_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        conversation_id = str(payload.get("conversation_id") or uuid.uuid4())
        now = utcnow()
        conversation = {
            "conversation_id": conversation_id,
            "customer_id": payload.get("customer_id"),
            "messages": payload.get("messages", []),
            "cart": payload.get("cart", {}),
            "created_at": payload.get("created_at") or now,
            "updated_at": payload.get("updated_at") or now,
        }
        return self._save(self.conversations, conversation)

    def update_conversation(self, conversation_id: str, updated: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_conversation(conversation_id)
        if not existing:
            raise KeyError(f"Unknown conversation: {conversation_id}")
        existing.update(updated)
        existing["updated_at"] = utcnow()
        return self._save(self.conversations, existing)

    def delete_conversation(self, conversation_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(self.conversations.delete().where(self.conversations.c.id == conversation_id))

    # Order operations include a payment-reference lookup for the demo payment page.
    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        order_id = str(payload.get("id") or f"TN-{uuid.uuid4().hex[:8].upper()}")
        now = utcnow()
        order = {
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
            "payment_reference": payload.get("payment_reference"),
            "tracking_url": payload.get("tracking_url"),
            "tracking_number": payload.get("tracking_number"),
            "shipping_address": payload.get("shipping_address", ""),
            "customer_name": payload.get("customer_name", ""),
            "email": payload.get("email", ""),
            "phone": payload.get("phone", ""),
            "created_at": payload.get("created_at") or now,
            "updated_at": payload.get("updated_at") or now,
        }
        return self._save(self.orders, order)

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        return self._get(self.orders, order_id)

    def get_order_by_payment_reference(self, payment_reference: str) -> dict[str, Any] | None:
        return next((order for order in self._all(self.orders) if order.get("payment_reference") == payment_reference), None)

    def get_order_by_customer(self, customer_id: str) -> list[dict[str, Any]]:
        return [order for order in self._all(self.orders) if order.get("customer_id") == customer_id]

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        order = self.get_order(order_id)
        if not order:
            raise NotFoundError(f"Order '{order_id}' was not found.")
        order.update(payload)
        order["updated_at"] = utcnow()
        return self._save(self.orders, order)

    @property
    def demo_customer_id(self) -> str:
        return self._demo_customer["id"]
