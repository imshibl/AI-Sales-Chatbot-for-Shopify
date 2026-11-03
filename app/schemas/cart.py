"""Request models for adding or changing conversation cart items."""

from __future__ import annotations

from pydantic import BaseModel


class CartItemRequest(BaseModel):
    """Identify a catalog product and the quantity to add."""

    product_id: str
    quantity: int = 1


class CartItemUpdateRequest(BaseModel):
    """Set a cart line to a positive quantity."""

    quantity: int
