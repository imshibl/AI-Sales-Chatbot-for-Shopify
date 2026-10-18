from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.exceptions import AppError
from app.repositories.memory import repository as repo
from app.schemas.cart import CartItemRequest, CartItemUpdateRequest
from app.services.cart_service import CartService

router = APIRouter()
service = CartService(repo)


@router.get("/cart/{conversation_id}")
def get_cart(conversation_id: str):
    try:
        return {"cart": service.get_cart(conversation_id)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.post("/cart/{conversation_id}/items")
def add_cart_item(conversation_id: str, payload: CartItemRequest):
    try:
        return {"cart": service.add_item(conversation_id, payload.product_id, payload.quantity)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.patch("/cart/{conversation_id}/items/{product_id}")
def update_cart_item(conversation_id: str, product_id: str, payload: CartItemUpdateRequest):
    try:
        return {"cart": service.update_item(conversation_id, product_id, payload.quantity)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.delete("/cart/{conversation_id}/items/{product_id}")
def remove_cart_item(conversation_id: str, product_id: str):
    try:
        return {"cart": service.remove_item(conversation_id, product_id)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc
