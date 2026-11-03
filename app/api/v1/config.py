"""Expose non-secret store branding required by the hosted frontend."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/config")
def public_store_config() -> dict[str, str | bool]:
    """Return only public display settings; never expose integration credentials."""
    return {
        "store_name": settings.store_name,
        "currency": settings.currency,
        "is_demo_catalog": settings.catalog_provider.lower() == "memory",
    }
