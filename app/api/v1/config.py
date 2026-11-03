from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/config")
def public_store_config() -> dict[str, str | bool]:
    return {
        "store_name": settings.store_name,
        "currency": settings.currency,
        "is_demo_catalog": settings.catalog_provider.lower() == "memory",
    }
