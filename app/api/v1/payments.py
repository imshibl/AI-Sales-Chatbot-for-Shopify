"""Development-only endpoints for inspecting and simulating demo payments."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.exceptions import AppError
from app.repositories.factory import repository as repo
from app.schemas.order import DemoPaymentCompleteRequest
from app.services.order_service import OrderService

router = APIRouter()
service = OrderService(repo)

# Guard every simulator route so it can be disabled outside development.
@router.get("/demo/payments/{payment_reference}")
def get_demo_payment(payment_reference: str):
    if not settings.enable_demo_payment_endpoint:
        raise HTTPException(status_code=403, detail={"message": "Demo payment simulation is disabled in this environment.", "error_code": "demo_disabled"})
    try:
        return service.get_payment_by_reference(payment_reference)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.post("/demo/payments/{order_id}/complete")
def complete_demo_payment(order_id: str, payload: DemoPaymentCompleteRequest):
    if not settings.enable_demo_payment_endpoint:
        raise HTTPException(status_code=403, detail={"message": "Demo payment simulation is disabled in this environment.", "error_code": "demo_disabled"})
    try:
        order = service.simulate_payment_outcome(order_id, payload.outcome)
        return {
            "order_id": order["id"],
            "payment_status": order["payment_status"],
            "order_status": order["order_status"],
        }
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc


@router.post("/demo/payments/{order_id}/simulate-success")
def simulate_demo_payment(order_id: str):
    if not settings.enable_demo_payment_endpoint:
        raise HTTPException(status_code=403, detail={"message": "Demo payment simulation is disabled in this environment.", "error_code": "demo_disabled"})
    try:
        return {"order": service.simulate_payment_success(order_id)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc
