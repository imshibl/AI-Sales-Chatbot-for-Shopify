from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.exceptions import AppError
from app.repositories.memory import repository as repo
from app.services.order_service import OrderService

router = APIRouter()
service = OrderService(repo)


@router.post("/demo/payments/{order_id}/simulate-success")
def simulate_demo_payment(order_id: str):
    if not settings.enable_demo_payment_endpoint:
        raise HTTPException(status_code=403, detail={"message": "Demo payment simulation is disabled in this environment.", "error_code": "demo_disabled"})
    try:
        return {"order": service.simulate_payment_success(order_id)}
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": exc.message, "error_code": exc.error_code}) from exc
