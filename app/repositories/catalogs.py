from __future__ import annotations

import logging
import re
import time
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import IntegrationError
from app.repositories.interfaces import BaseRepository

logger = logging.getLogger(__name__)


class ProductCatalog:
    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        return next((product for product in self.list_products(active_only=False) if product["id"] == product_id), None)

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
        products = self.list_products(active_only=active_only)
        if category:
            products = [item for item in products if item.get("category", "").lower() == category.lower()]
        if skin_type:
            products = [item for item in products if skin_type.lower() in [value.lower() for value in item.get("skin_types", [])]]
        if concern:
            products = [item for item in products if concern.lower() in [value.lower() for value in item.get("concerns", [])]]
        if max_price is not None:
            products = [item for item in products if item["price"] <= max_price]
        needle = (query or "").lower()
        if needle:
            products = [
                item for item in products
                if needle in item["name"].lower()
                or needle in item["category"].lower()
                or needle in item["description"].lower()
                or any(needle in value.lower() for field in ("ingredients", "benefits", "concerns", "skin_types") for value in item[field])
            ]
        return products


class MemoryProductCatalog(ProductCatalog):
    def __init__(self, repository: BaseRepository):
        self.repository = repository

    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        return self.repository.list_products(active_only=active_only)

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        return self.repository.get_product(product_id)

    def search_products(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.search_products(**filters)


class CachedProductCatalog(ProductCatalog):
    def __init__(self, cache_seconds: int):
        self.cache_seconds = max(cache_seconds, 0)
        self._cached_products: list[dict[str, Any]] | None = None
        self._cache_expires_at = 0.0

    def load_products(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        now = time.monotonic()
        if self._cached_products is None or now >= self._cache_expires_at:
            self._cached_products = self.load_products()
            self._cache_expires_at = now + self.cache_seconds
        return [
            dict(product) for product in self._cached_products
            if not active_only or product.get("is_active", True)
        ]


class ShopifyProductCatalog(CachedProductCatalog):
    def __init__(self, domain: str, access_token: str, api_version: str, cache_seconds: int):
        super().__init__(cache_seconds)
        parsed_domain = urlparse(f"https://{domain.strip()}")
        if not domain.strip() or not parsed_domain.hostname or parsed_domain.path != "/":
            raise ValueError("SHOPIFY_STORE_DOMAIN must be a hostname such as your-store.myshopify.com.")
        if not access_token.strip():
            raise ValueError("SHOPIFY_STOREFRONT_ACCESS_TOKEN is required for the Shopify catalog.")
        self.endpoint = f"https://{parsed_domain.hostname}/api/{api_version}/graphql.json"
        self.access_token = access_token

    def load_products(self) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        cursor: str | None = None
        query = """
        query Products($cursor: String) {
          products(first: 250, after: $cursor) {
            edges {
              cursor
              node {
                id title handle description productType tags availableForSale
                featuredImage { url }
                priceRange { minVariantPrice { amount currencyCode } }
              }
            }
            pageInfo { hasNextPage }
          }
        }
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                while True:
                    response = client.post(
                        self.endpoint,
                        headers={"X-Shopify-Storefront-Access-Token": self.access_token},
                        json={"query": query, "variables": {"cursor": cursor}},
                    )
                    response.raise_for_status()
                    body = response.json()
                    if body.get("errors"):
                        raise IntegrationError("Shopify returned an error while loading products.")
                    connection = body["data"]["products"]
                    for edge in connection["edges"]:
                        source = edge["node"]
                        source_currency = source["priceRange"]["minVariantPrice"]["currencyCode"]
                        if source_currency.upper() != settings.currency.upper():
                            raise IntegrationError(
                                f"Shopify product currency {source_currency} does not match configured CURRENCY."
                            )
                        products.append(self._map_product(source))
                    if not connection["pageInfo"]["hasNextPage"]:
                        return products
                    if not connection["edges"]:
                        raise IntegrationError("Shopify indicated another product page but returned no cursor.")
                    cursor = connection["edges"][-1]["cursor"]
        except IntegrationError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.exception("Unable to load the Shopify product catalog.")
            raise IntegrationError("Unable to load the Shopify product catalog. Check the store configuration and try again.") from exc

    @staticmethod
    def _map_product(source: dict[str, Any]) -> dict[str, Any]:
        tags = source.get("tags", [])
        price = source["priceRange"]["minVariantPrice"]["amount"]
        try:
            normalized_price = _amount(Decimal(str(price)))
        except (InvalidOperation, ValueError) as exc:
            raise IntegrationError("Shopify returned a product with an invalid price.") from exc
        return {
            "id": source["id"],
            "name": source["title"],
            "slug": source["handle"],
            "category": source.get("productType") or "general",
            "description": source.get("description", ""),
            "ingredients": [],
            "benefits": tags,
            "skin_types": [tag.split(":", 1)[1].strip() for tag in tags if tag.lower().startswith("skin_type:")],
            "concerns": [tag.split(":", 1)[1].strip() for tag in tags if tag.lower().startswith("concern:")],
            "how_to_use": "",
            "precautions": "",
            "price": normalized_price,
            "original_price": normalized_price,
            "stock_quantity": None if source.get("availableForSale") else 0,
            "image_url": (source.get("featuredImage") or {}).get("url"),
            "is_active": bool(source.get("availableForSale")),
            "rating": 0.0,
            "review_count": 0,
        }


class RESTProductCatalog(CachedProductCatalog):
    def __init__(
        self,
        url: str,
        token: str,
        cache_seconds: int,
        api_type: str = "rest",
        graphql_query: str = "",
    ):
        super().__init__(cache_seconds)
        api_type = api_type.lower()
        if not url.strip():
            raise ValueError("CATALOG_API_URL is required for the custom API catalog.")
        if api_type not in {"rest", "graphql"}:
            raise ValueError("CATALOG_API_TYPE must be either 'rest' or 'graphql'.")
        if api_type == "graphql" and not graphql_query.strip():
            raise ValueError("CATALOG_API_QUERY is required for a GraphQL catalog.")
        self.url = url
        self.token = token
        self.api_type = api_type
        self.graphql_query = graphql_query

    def load_products(self) -> list[dict[str, Any]]:
        headers = {"Authorization": "Bearer " + self.token} if self.token else {}
        try:
            if self.api_type == "graphql":
                response = httpx.post(
                    self.url,
                    headers=headers,
                    json={"query": self.graphql_query},
                    timeout=10.0,
                )
            else:
                response = httpx.get(self.url, headers=headers, timeout=10.0)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.exception("Unable to load the custom API product catalog.")
            raise IntegrationError("Unable to load the custom API product catalog. Check the endpoint and credentials.") from exc
        if self.api_type == "graphql":
            if not isinstance(body, dict) or body.get("errors"):
                raise IntegrationError("The GraphQL catalog returned an error.")
            data = body.get("data")
            source_products = data.get("products") if isinstance(data, dict) else None
            if isinstance(source_products, dict):
                edges = source_products.get("edges")
                if not isinstance(edges, list) or any(
                    not isinstance(edge, dict) or not isinstance(edge.get("node"), dict)
                    for edge in edges
                ):
                    raise IntegrationError("GraphQL product connections must return objects in 'edges[].node'.")
                source_products = [edge["node"] for edge in edges]
        else:
            source_products = body.get("products") if isinstance(body, dict) else body
        if not isinstance(source_products, list):
            raise IntegrationError("The custom API must return an array of canonical products under 'products'.")
        return [_normalize_product(product) for product in source_products]


class SQLProductCatalog(CachedProductCatalog):
    def __init__(self, database_url: str, query: str, cache_seconds: int):
        super().__init__(cache_seconds)
        if not database_url.strip():
            raise ValueError("CATALOG_DATABASE_URL is required for the SQL catalog.")
        if not re.match(r"(?is)^select\b", query.strip()):
            raise ValueError("CATALOG_SQL_QUERY must be a SELECT statement.")
        self.engine = create_engine(database_url)
        self.query = text(query)

    def load_products(self) -> list[dict[str, Any]]:
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(self.query).mappings().all()
        except SQLAlchemyError as exc:
            logger.exception("Unable to load products from the configured SQL catalog.")
            raise IntegrationError("Unable to load products from the configured SQL catalog. Check the query and database access.") from exc
        return [_normalize_product(dict(row)) for row in rows]


def _normalize_product(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise IntegrationError("Each catalog product must be an object.")
    if source.get("id") is None or source.get("name") is None:
        raise IntegrationError("Catalog products must provide non-empty 'id' and 'name' fields.")
    available = source.get("is_active", True)
    if not isinstance(available, bool):
        raise IntegrationError("Catalog product 'is_active' values must be boolean.")
    try:
        product_id = str(source["id"])
        name = str(source["name"])
        price = _amount(Decimal(str(source["price"])))
        original_price = _amount(Decimal(str(source.get("original_price", price))))
        stock_quantity = (
            int(source["stock_quantity"])
            if source.get("stock_quantity") is not None
            else None if available else 0
        )
        rating = float(source.get("rating", 0))
        review_count = int(source.get("review_count", 0))
    except (KeyError, InvalidOperation, ValueError, TypeError, OverflowError) as exc:
        raise IntegrationError("Catalog products must provide valid 'id', 'name', and 'price' fields.") from exc
    if (
        not product_id.strip()
        or not name.strip()
        or min(price, original_price, review_count) < 0
        or (stock_quantity is not None and stock_quantity < 0)
        or not isfinite(rating)
        or rating < 0
    ):
        raise IntegrationError("Catalog product IDs and names must be non-empty and numeric fields cannot be negative.")
    values = {
        "id": product_id,
        "name": name,
        "slug": str(source.get("slug", product_id)),
        "category": str(source.get("category", "general")),
        "description": str(source.get("description", "")),
        "ingredients": source.get("ingredients", []),
        "benefits": source.get("benefits", []),
        "skin_types": source.get("skin_types", []),
        "concerns": source.get("concerns", []),
        "how_to_use": str(source.get("how_to_use", "")),
        "precautions": str(source.get("precautions", "")),
        "price": price,
        "original_price": original_price,
        "stock_quantity": stock_quantity,
        "image_url": source.get("image_url"),
        "is_active": available,
        "rating": rating,
        "review_count": review_count,
    }
    if any(not isinstance(values[field], list) for field in ("ingredients", "benefits", "skin_types", "concerns")):
        raise IntegrationError(f"Catalog product '{product_id}' list fields must be arrays.")
    if any(not isinstance(value, str) for field in ("ingredients", "benefits", "skin_types", "concerns") for value in values[field]):
        raise IntegrationError(f"Catalog product '{product_id}' list fields must contain strings.")
    return values


def _amount(value: Decimal) -> int | float:
    if not value.is_finite() or value < 0:
        raise ValueError("Price must be a non-negative finite amount.")
    if value == value.to_integral_value():
        return int(value)
    amount = float(value)
    if not isfinite(amount):
        raise ValueError("Price is outside the supported numeric range.")
    return amount


class CatalogRepository:
    def __init__(self, storage: BaseRepository, catalog: ProductCatalog):
        self.storage = storage
        self.catalog = catalog

    def __getattr__(self, name: str) -> Any:
        return getattr(self.storage, name)

    def list_products(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        return self.catalog.list_products(active_only=active_only)

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        return self.catalog.get_product(product_id)

    def search_products(self, **filters: Any) -> list[dict[str, Any]]:
        return self.catalog.search_products(**filters)


def create_catalog(storage: BaseRepository) -> ProductCatalog:
    provider = settings.catalog_provider.lower()
    if provider == "memory":
        return MemoryProductCatalog(storage)
    if provider == "shopify":
        return ShopifyProductCatalog(
            settings.shopify_store_domain,
            settings.shopify_storefront_access_token,
            settings.shopify_api_version,
            settings.catalog_cache_seconds,
        )
    if provider == "rest":
        return RESTProductCatalog(
            settings.catalog_api_url,
            settings.catalog_api_token,
            settings.catalog_cache_seconds,
            settings.catalog_api_type,
            settings.catalog_api_query,
        )
    if provider == "sql":
        return SQLProductCatalog(
            settings.catalog_database_url,
            settings.catalog_sql_query,
            settings.catalog_cache_seconds,
        )
    raise ValueError("CATALOG_PROVIDER must be one of: memory, shopify, rest, sql.")
