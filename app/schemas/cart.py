from __future__ import annotations

from pydantic import BaseModel


class CartItemRequest(BaseModel):
    product_id: str
    quantity: int = 1


class CartItemUpdateRequest(BaseModel):
    quantity: int
