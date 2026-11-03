"""Structural contract shared by storage backends and service consumers."""

from __future__ import annotations

from typing import Any, Protocol


class BaseRepository(Protocol):
    """Describe catalog, customer, conversation, and order operations."""

    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        ...

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        ...

    def search_products(self, *, query: str | None = None, category: str | None = None,
                        skin_type: str | None = None, concern: str | None = None,
                        max_price: float | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        ...

    def create_customer(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        ...

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        ...

    def create_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def update_conversation(self, conversation_id: str, updated: dict[str, Any]) -> dict[str, Any]:
        ...

    def delete_conversation(self, conversation_id: str) -> None:
        ...

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        ...

    def get_order_by_customer(self, customer_id: str) -> list[dict[str, Any]]:
        ...

    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_order_by_payment_reference(self, payment_reference: str) -> dict[str, Any] | None:
        ...

    demo_customer_id: str
    store_policies: dict[str, Any]
