from __future__ import annotations

from app.core.exceptions import NotFoundError
from app.repositories.memory import MemoryRepository, repository

repo = repository


class ProductService:
    def __init__(self, repository: MemoryRepository | None = None):
        self.repository = repository or repo

    def list_products(self, *, category: str | None = None, skin_type: str | None = None,
                      concern: str | None = None, max_price: int | None = None) -> list[dict]:
        return self.repository.search_products(
            query=None,
            category=category,
            skin_type=skin_type,
            concern=concern,
            max_price=max_price,
            active_only=True,
        )

    def get_product(self, product_id: str) -> dict:
        product = self.repository.get_product(product_id)
        if not product:
            raise NotFoundError(f"Product '{product_id}' was not found.")
        return product

    def search_products(self, *, query: str | None = None, category: str | None = None,
                        skin_type: str | None = None, concern: str | None = None,
                        max_price: int | None = None, limit: int | None = None) -> list[dict]:
        results = self.repository.search_products(
            query=query,
            category=category,
            skin_type=skin_type,
            concern=concern,
            max_price=max_price,
            active_only=True,
        )
        if limit is not None:
            return results[:limit]
        return results

    def get_shipping_policy(self) -> dict:
        return self.repository.store_policies.get("shipping", {})

    def get_store_policies(self) -> dict:
        return self.repository.store_policies
