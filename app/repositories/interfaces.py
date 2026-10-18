from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseRepository(ABC):
    @abstractmethod
    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_product(self, product_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def search_products(self, *, query: str | None = None, category: str | None = None,
                        skin_type: str | None = None, concern: str | None = None,
                        max_price: int | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def create_customer(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def create_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_conversation(self, conversation_id: str, updated: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete_conversation(self, conversation_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def get_order_by_customer(self, customer_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def update_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
