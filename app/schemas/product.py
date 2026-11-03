"""Query and response models for the storefront product catalog."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductListQuery(BaseModel):
    """Optional catalog filters accepted by product-listing clients."""

    category: str | None = None
    skin_type: str | None = None
    concern: str | None = None
    max_price: float | None = None
    available_only: bool = True


class ProductCard(BaseModel):
    """Compact product data shape used by recommendation cards."""

    id: str
    name: str
    price: float
    description: str
    benefits: list[str]
    image_url: str | None = None
    availability: str = "in stock"
