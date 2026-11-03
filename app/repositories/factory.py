from __future__ import annotations

import json

from app.core.config import settings
from app.repositories.catalogs import CatalogRepository, create_catalog
from app.repositories.memory import MemoryRepository
from app.repositories.sqlalchemy_repository import SQLAlchemyRepository


def create_repository() -> CatalogRepository:
    backend = settings.storage_backend.lower()
    if backend == "memory":
        storage = MemoryRepository()
    elif backend == "sql":
        storage = SQLAlchemyRepository(settings.database_url)
    else:
        raise ValueError("STORAGE_BACKEND must be either 'memory' or 'sql'.")
    if settings.store_policies_json.strip():
        try:
            policies = json.loads(settings.store_policies_json)
        except json.JSONDecodeError as exc:
            raise ValueError("STORE_POLICIES_JSON must contain a valid JSON object.") from exc
        if not isinstance(policies, dict):
            raise ValueError("STORE_POLICIES_JSON must contain a JSON object.")
        if "shipping" in policies and not isinstance(policies["shipping"], dict):
            raise ValueError("STORE_POLICIES_JSON 'shipping' value must be a JSON object.")
        storage.store_policies = policies
    elif settings.catalog_provider.lower() != "memory":
        storage.store_policies = {
            "shipping": {
                "shipping_fee": settings.default_shipping_fee,
                "free_shipping_threshold": settings.default_free_shipping_threshold,
            }
        }
    else:
        storage.store_policies.setdefault("shipping", {}).update({
            "shipping_fee": settings.default_shipping_fee,
            "free_shipping_threshold": settings.default_free_shipping_threshold,
        })
    return CatalogRepository(storage, create_catalog(storage))


repository = create_repository()
