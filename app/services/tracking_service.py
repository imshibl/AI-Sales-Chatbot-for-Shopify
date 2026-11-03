from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.factory import repository
from app.repositories.interfaces import BaseRepository

repo = repository


class TrackingService:
    def __init__(self, repository: BaseRepository | None = None):
        self.repository = repository or repo

    def get_tracking(self, order_id: str, customer_id: str | None = None) -> dict:
        order = self.repository.get_order(order_id)
        if not order:
            raise NotFoundError(f"Order '{order_id}' was not found.")
        if customer_id and order.get("customer_id") != customer_id:
            raise ValidationError("This order is not available for the current customer.")

        tracking_number = order.get("tracking_number") or f"TN-TRACK-{order_id.split('-')[-1]}"
        tracking_url = order.get("tracking_url") or f"https://demo.thainaturals.local/track-demo/{tracking_number}"
        return {
            "order_id": order_id,
            "status": order.get("order_status", "pending_payment"),
            "tracking_number": tracking_number,
            "tracking_url": tracking_url,
            "estimated_delivery": "3-6 business days",
        }
