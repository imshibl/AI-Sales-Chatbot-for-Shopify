from __future__ import annotations

from typing import Any

from app.payments.interfaces import PaymentProvider


class DummyPaymentProvider(PaymentProvider):
    def __init__(self) -> None:
        self._statuses: dict[str, str] = {}

    def create_payment_link(self, order: dict[str, Any]) -> dict[str, Any]:
        payment_reference = f"DEMO-{order['id']}-{abs(hash(order['id'])) % 100000}"
        payment_url = f"https://demo.thainaturals.local/payments/{payment_reference}?demo=1"
        self._statuses[payment_reference] = "pending"
        return {
            "payment_reference": payment_reference,
            "payment_url": payment_url,
            "status": "pending",
        }

    def get_payment_status(self, payment_reference: str) -> str:
        return self._statuses.get(payment_reference, "pending")

    def simulate_success(self, payment_reference: str) -> str:
        self._statuses[payment_reference] = "paid"
        return self._statuses[payment_reference]
