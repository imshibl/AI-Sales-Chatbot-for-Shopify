from __future__ import annotations

from pydantic import BaseModel, Field


class ProductListQuery(BaseModel):
    category: str | None = None
    skin_type: str | None = None
    concern: str | None = None
    max_price: int | None = None
    available_only: bool = True


class ProductCard(BaseModel):
    id: str
    name: str
    price: int
    description: str
    benefits: list[str]
    image_url: str | None = None
    availability: str = "in stock"
