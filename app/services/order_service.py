"""Prepare confirmed orders, create demo payment links, and refresh order status."""

from __future__ import annotations

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.payments.dummy_provider import DummyPaymentProvider
from app.repositories.factory import repository
from app.repositories.interfaces import BaseRepository
from app.services.cart_service import CartService

repo = repository
_default_payment_provider = DummyPaymentProvider()
cart_service = CartService(repo)


class OrderService:
    """Coordinate cart validation, persisted order records, and payment provider calls."""

    def __init__(self, repository: BaseRepository | None = None, payment_provider=None):
        self.repository = repository or repo
        self.payment_provider = payment_provider or _default_payment_provider
        self.cart_service = CartService(self.repository)

    def preview_order(self, conversation_id: str, shipping_address: str | None = None) -> dict:
        cart = self.cart_service.validate_cart_for_checkout(conversation_id)
        if not shipping_address:
            customer = self.repository.get_customer(self.repository.demo_customer_id)
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

    def prepare_checkout(
        self,
        conversation_id: str,
        customer_name: str,
        email: str,
        phone: str,
        shipping_address: str,
        turn_id: str,
    ) -> dict:
        # Save a price snapshot so later confirmation cannot silently approve changed totals.
        contact = {
            "customer_name": customer_name.strip(),
            "email": email.strip(),
            "phone": phone.strip(),
            "shipping_address": shipping_address.strip(),
        }
        if not all(contact.values()):
            raise ValidationError("Please provide your name, email, phone number, and full delivery address.")
        preview = self.preview_order(conversation_id, contact["shipping_address"])
        conversation = self.repository.get_conversation(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation '{conversation_id}' was not found.")
        self.repository.update_conversation(
            conversation_id,
            {
                "pending_checkout": {
                    **contact,
                    "prepared_turn_id": turn_id,
                    "summary_presented": False,
                    "order_snapshot": {
                        key: preview[key]
                        for key in ("items", "subtotal", "shipping_fee", "discount", "total", "currency")
                    },
                }
            },
        )
        return {
            "items": preview["items"],
            "subtotal": preview["subtotal"],
            "shipping_fee": preview["shipping_fee"],
            "discount": preview["discount"],
            "total": preview["total"],
            "currency": preview["currency"],
            "customer_name": contact["customer_name"],
            "email": contact["email"],
            "phone": contact["phone"],
            "shipping_address": contact["shipping_address"],
            "payment_status": "pending",
            "order_status": "pending_payment",
        }

    def place_prepared_order(
        self,
        conversation_id: str,
        turn_id: str,
        confirmed: bool,
        customer_id: str | None = None,
    ) -> dict:
        # Require a later-turn confirmation and an unchanged cart before order creation.
        conversation = self.repository.get_conversation(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation '{conversation_id}' was not found.")
        pending = conversation.get("pending_checkout")
        if not pending:
            raise ValidationError("Collect the customer's contact and delivery details and confirm the order summary first.")
        if pending.get("prepared_turn_id") == turn_id:
            raise ValidationError("Show the order summary and wait for the customer's confirmation in a separate message.")
        if not pending.get("summary_presented"):
            raise ValidationError("Present the prepared order summary to the customer before asking for confirmation.")
        if not confirmed:
            raise ValidationError("The customer must explicitly confirm the order before it is created.")
        current_preview = self.preview_order(conversation_id, pending["shipping_address"])
        snapshot = pending.get("order_snapshot", {})
        if any(
            current_preview[key] != snapshot.get(key)
            for key in ("items", "subtotal", "shipping_fee", "discount", "total", "currency")
        ):
            raise ConflictError("The cart changed after the summary. Prepare and confirm the updated order before placing it.")
        order = self.create_order(
            conversation_id,
            shipping_address=pending["shipping_address"],
            customer_id=customer_id,
            confirmed=True,
            customer_name=pending["customer_name"],
            email=pending["email"],
            phone=pending["phone"],
        )
        self.repository.update_conversation(conversation_id, {"pending_checkout": None})
        return order

    def create_order(
        self,
        conversation_id: str,
        shipping_address: str | None = None,
        customer_id: str | None = None,
        confirmed: bool = False,
        customer_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> dict:
        # The API and AI tool share this path, so confirmation/contact checks stay centralized.
        if not confirmed:
            raise ValidationError("Order creation requires explicit customer confirmation.")
        if not all(value and value.strip() for value in (customer_name, email, phone, shipping_address)):
            raise ValidationError("Order creation requires the customer's name, email, phone number, and delivery address.")

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
            "customer_name": customer_name.strip(),
            "email": email.strip(),
            "phone": phone.strip(),
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
        order = self.refresh_payment_status(order_id, customer_id=customer_id)
        if order.get("payment_status") != "paid":
            return {
                "order_id": order_id,
                "status": order.get("order_status", "pending_payment"),
                "tracking_number": None,
                "tracking_url": None,
                "estimated_delivery": None,
            }
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

    def refresh_payment_status(self, order_id: str, customer_id: str | None = None) -> dict:
        # Provider status is authoritative; customer text never marks an order as paid.
        order = self.get_order(order_id, customer_id=customer_id)
        if order.get("payment_status") == "paid":
            return order
        payment_reference = order.get("payment_reference")
        if not payment_reference:
            return order
        status = self.payment_provider.get_payment_status(payment_reference)
        if status == "paid":
            return self._mark_order_paid(order_id)
        if status in {"pending", "failed", "cancelled"} and status != order.get("payment_status"):
            return self.repository.update_order(
                order_id,
                {
                    "payment_status": status,
                    "order_status": "payment_failed" if status in {"failed", "cancelled"} else "pending_payment",
                },
            )
        return order

    def list_customer_orders(self, customer_id: str | None = None) -> dict:
        customer_id = customer_id or self.repository.demo_customer_id
        orders = self.repository.get_order_by_customer(customer_id)
        orders.sort(key=lambda order: order.get("created_at", ""), reverse=True)
        orders = [self.refresh_payment_status(order["id"], customer_id) for order in orders]
        terminal_statuses = {"delivered", "cancelled", "payment_failed", "refunded"}
        return {
            "active_orders": [order for order in orders if order.get("order_status") not in terminal_statuses],
            "order_history": orders,
        }

    def get_payment_by_reference(self, payment_reference: str) -> dict:
        order = self.repository.get_order_by_payment_reference(payment_reference)
        if not order:
            raise NotFoundError("This demo payment link was not found.")
        order = self.refresh_payment_status(order["id"])
        return {
            "order_id": order["id"],
            "payment_reference": payment_reference,
            "payment_status": order["payment_status"],
            "order_status": order["order_status"],
            "amount": order["total"],
            "currency": order["currency"],
            "items": order["items"],
        }

    def simulate_payment_outcome(self, order_id: str, outcome: str) -> dict:
        order = self.get_order(order_id)
        payment_reference = order.get("payment_reference")
        if not payment_reference:
            raise ConflictError("This order does not have a payment reference.")
        if order.get("payment_status") == "paid":
            return order
        if outcome == "paid":
            self.payment_provider.simulate_success(payment_reference)
        elif outcome == "failed":
            self.payment_provider.simulate_failure(payment_reference)
        elif outcome == "pending":
            self.payment_provider.reset(payment_reference)
        else:
            raise ValidationError("Payment outcome must be paid, failed, or pending.")
        return self.refresh_payment_status(order_id)

    def simulate_payment_success(self, order_id: str) -> dict:
        updated = self.simulate_payment_outcome(order_id, "paid")
        if updated.get("payment_status") != "paid":
            raise ConflictError("Payment has not been verified as complete.")
        return updated

    def _mark_order_paid(self, order_id: str) -> dict:
        """Apply the demo fulfillment transition after the provider confirms payment."""
        tracking_number = "TN-TRACK-" + order_id.split("-")[-1]
        return self.repository.update_order(
            order_id,
            {
                "payment_status": "paid",
                "order_status": "confirmed",
                "tracking_number": tracking_number,
                "tracking_url": f"https://demo.thainaturals.local/track-demo/{tracking_number}",
            },
        )
