from __future__ import annotations

from pydantic import BaseModel


class OrderPreviewRequest(BaseModel):
    conversation_id: str
    shipping_address: str | None = None


class OrderConfirmationRequest(BaseModel):
    conversation_id: str
    customer_id: str | None = None
    shipping_address: str | None = None
    confirmed: bool = False


class DemoPaymentSimulateRequest(BaseModel):
    payment_reference: str | None = None
