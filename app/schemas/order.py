from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator


class OrderPreviewRequest(BaseModel):
    conversation_id: str
    shipping_address: str | None = None


class OrderConfirmationRequest(BaseModel):
    conversation_id: str
    customer_id: str | None = None
    shipping_address: str = Field(min_length=10, max_length=500)
    customer_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=7, max_length=32)
    confirmed: bool = False

    @field_validator("customer_name", "email", "phone", "shipping_address")
    @classmethod
    def strip_contact_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not re.fullmatch(r"[+()\d.\-\s]{7,32}", value) or len(re.sub(r"\D", "", value)) < 7:
            raise ValueError("Enter a valid phone number.")
        return value


class DemoPaymentSimulateRequest(BaseModel):
    payment_reference: str | None = None


class DemoPaymentCompleteRequest(BaseModel):
    outcome: str

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: str) -> str:
        if value not in {"paid", "failed", "pending"}:
            raise ValueError("Outcome must be paid, failed, or pending.")
        return value
