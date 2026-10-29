from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.exceptions import AppError
from app.repositories.memory import repository as repo
from app.schemas.order import OrderConfirmationRequest, OrderPreviewRequest
from app.services.order_service import OrderService

router = APIRouter()
service = OrderService(repo)


@router.post("/orders/preview")
def preview_order(payload: OrderPreviewRequest):
    try:
        return service.preview_order(payload.conversation_id, payload.shipping_address)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.post("/orders")
def create_order(payload: OrderConfirmationRequest):
    try:
        return service.create_order(
            payload.conversation_id,
            payload.shipping_address,
            payload.customer_id,
            payload.confirmed,
            payload.customer_name,
            payload.email,
            payload.phone,
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.get("/orders")
def list_orders():
    try:
        return service.list_customer_orders()
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.get("/orders/{order_id}")
def get_order(order_id: str):
    try:
        return {"order": service.refresh_payment_status(order_id)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.get("/orders/{order_id}/payment-status")
def payment_status(order_id: str):
    try:
        order = service.refresh_payment_status(order_id)
        return {
            "order_id": order["id"],
            "payment_status": order.get("payment_status"),
            "order_status": order.get("order_status"),
        }
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.get("/orders/{order_id}/tracking")
def track_order(order_id: str):
    try:
        return service.get_tracking_information(order_id)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc
