from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationError
from app.payments.dummy_provider import DummyPaymentProvider
from app.repositories.memory import MemoryRepository, repository
from app.services.cart_service import CartService

repo = repository
payment_provider = DummyPaymentProvider()
cart_service = CartService(repo)


class OrderService:
    def __init__(self, repository: MemoryRepository | None = None, payment_provider=None):
        self.repository = repository or repo
        self.payment_provider = payment_provider or DummyPaymentProvider()
        self.cart_service = CartService(self.repository)

    def preview_order(self, conversation_id: str, shipping_address: str | None = None) -> dict:
        cart = self.cart_service.validate_cart_for_checkout(conversation_id)
        if not shipping_address:
            customer = self.repository.customers.get(self.repository.demo_customer_id)
            shipping_address = customer.get("shipping_address") if customer else "" 
        return {
            "items": cart["items"],
            "subtotal": cart["subtotal"],
            "shipping_fee": cart["shipping_fee"],
            "discount": cart["discount"],
            "total": cart["total"],
            "currency": cart["currency"],
            "shipping_address": shipping_address,
            "payment_status": "pending",
            "order_status": "pending_payment",
        }

    def create_order(self, conversation_id: str, shipping_address: str | None = None, customer_id: str | None = None, confirmed: bool = False) -> dict:
        if not confirmed:
            raise ValidationError("Order creation requires explicit customer confirmation.")

        conv = self.repository.get_conversation(conversation_id)
        if not conv:
            raise NotFoundError(f"Conversation '{conversation_id}' was not found.")

        customer_id = customer_id or self.repository.demo_customer_id
        customer = self.repository.get_customer(customer_id)
        if not customer:
            raise NotFoundError(f"Customer '{customer_id}' was not found.")

        preview = self.preview_order(conversation_id, shipping_address or customer.get("shipping_address"))
        order_payload = {
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": item["product_id"],
                    "product_name": item["product_name"],
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                    "line_total": item["line_total"],
                }
                for item in preview["items"]
            ],
            "subtotal": preview["subtotal"],
            "shipping_fee": preview["shipping_fee"],
            "discount": preview["discount"],
            "total": preview["total"],
            "currency": preview["currency"],
            "payment_status": "pending",
            "order_status": "pending_payment",
            "payment_url": None,
            "tracking_url": None,
            "tracking_number": None,
            "shipping_address": preview["shipping_address"],
        }

        order = self.repository.create_order(order_payload)
        payment = self.payment_provider.create_payment_link(order)
        order["payment_url"] = payment["payment_url"]
        order["payment_reference"] = payment["payment_reference"]
        self.repository.update_order(order["id"], {"payment_url": payment["payment_url"], "payment_reference": payment["payment_reference"]})
        self.repository.update_conversation(conversation_id, {"cart": {}})
        return order

    def get_order(self, order_id: str, customer_id: str | None = None) -> dict:
        order = self.repository.get_order(order_id)
        if not order:
            raise NotFoundError(f"Order '{order_id}' was not found.")
        if customer_id and order.get("customer_id") != customer_id:
            raise ValidationError("This order is not available for the current customer.")
        return order

    def get_tracking_information(self, order_id: str, customer_id: str | None = None) -> dict:
        order = self.get_order(order_id, customer_id=customer_id)
        tracking_number = order.get("tracking_number") or "TN-TRACK-" + order_id.split("-")[-1]
        tracking_url = order.get("tracking_url") or "https://demo.thainaturals.local/track-demo/" + tracking_number
        status = order.get("order_status", "pending_payment")
        return {
            "order_id": order_id,
            "status": status,
            "tracking_number": tracking_number,
            "tracking_url": tracking_url,
            "estimated_delivery": "3-6 business days",
        }

    def simulate_payment_success(self, order_id: str) -> dict:
        order = self.repository.get_order(order_id)
        if not order:
            raise NotFoundError(f"Order '{order_id}' was not found.")
        updated = self.repository.update_order(
            order_id,
            {
                "payment_status": "paid",
                "order_status": "confirmed",
                "tracking_number": "TN-TRACK-" + order_id.split("-")[-1],
                "tracking_url": "https://demo.thainaturals.local/track-demo/TN-TRACK-" + order_id.split("-")[-1],
            },
        )
        return updated
