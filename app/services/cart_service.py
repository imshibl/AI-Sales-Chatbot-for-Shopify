from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.memory import MemoryRepository, repository

repo = repository


class CartService:
    def __init__(self, repository: MemoryRepository | None = None):
        self.repository = repository or repo

    def get_cart(self, conversation_id: str) -> dict:
        conversation = self.repository.get_conversation(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation '{conversation_id}' was not found.")
        return conversation.get("cart", {})

    def _ensure_conversation(self, conversation_id: str):
        conversation = self.repository.get_conversation(conversation_id)
        if not conversation:
            raise NotFoundError(f"Conversation '{conversation_id}' was not found.")
        return conversation

    def add_item(self, conversation_id: str, product_id: str, quantity: int = 1) -> dict:
        conversation = self._ensure_conversation(conversation_id)
        product = self.repository.get_product(product_id)
        if not product:
            raise NotFoundError(f"Product '{product_id}' was not found.")
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        if product["stock_quantity"] < quantity:
            raise ValidationError(f"Only {product['stock_quantity']} units remain for {product['name']}.")

        cart = conversation.get("cart", {})
        existing = cart.get(product_id, {"product_id": product_id, "quantity": 0})
        new_quantity = existing["quantity"] + quantity
        if new_quantity > product["stock_quantity"]:
            raise ValidationError(f"Cart exceeds available stock for {product['name']}.")
        existing["quantity"] = new_quantity
        cart[product_id] = existing
        conversation["cart"] = cart
        self.repository.update_conversation(conversation_id, {"cart": cart})
        return cart

    def update_item(self, conversation_id: str, product_id: str, quantity: int) -> dict:
        conversation = self._ensure_conversation(conversation_id)
        product = self.repository.get_product(product_id)
        if not product:
            raise NotFoundError(f"Product '{product_id}' was not found.")
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        if quantity > product["stock_quantity"]:
            raise ValidationError(f"Only {product['stock_quantity']} units remain for {product['name']}.")

        cart = conversation.get("cart", {})
        if product_id not in cart:
            raise NotFoundError(f"Product '{product_id}' is not in the cart.")
        cart[product_id] = {"product_id": product_id, "quantity": quantity}
        conversation["cart"] = cart
        self.repository.update_conversation(conversation_id, {"cart": cart})
        return cart

    def remove_item(self, conversation_id: str, product_id: str) -> dict:
        conversation = self._ensure_conversation(conversation_id)
        cart = conversation.get("cart", {})
        if product_id not in cart:
            raise NotFoundError(f"Product '{product_id}' is not in the cart.")
        del cart[product_id]
        conversation["cart"] = cart
        self.repository.update_conversation(conversation_id, {"cart": cart})
        return cart

    def calculate_total(self, conversation_id: str, shipping_fee: int = 50) -> dict:
        conversation = self._ensure_conversation(conversation_id)
        cart = conversation.get("cart", {})
        items = []
        subtotal = 0

        for product_id, entry in cart.items():
            product = self.repository.get_product(product_id)
            if not product:
                continue
            quantity = int(entry.get("quantity", 0))
            item_total = product["price"] * quantity
            subtotal += item_total
            items.append({
                "product_id": product_id,
                "product_name": product["name"],
                "quantity": quantity,
                "unit_price": product["price"],
                "line_total": item_total,
            })

        free_shipping_threshold = self.repository.store_policies.get("shipping", {}).get("free_shipping_threshold", 1499)
        shipping = 0 if subtotal >= free_shipping_threshold else shipping_fee
        total = subtotal + shipping
        return {
            "subtotal": subtotal,
            "shipping_fee": shipping,
            "discount": 0,
            "total": total,
            "currency": "INR",
            "items": items,
        }

    def validate_cart_for_checkout(self, conversation_id: str) -> dict:
        conversation = self._ensure_conversation(conversation_id)
        cart = conversation.get("cart", {})
        if not cart:
            raise ValidationError("Your cart is empty.")
        for product_id, entry in cart.items():
            product = self.repository.get_product(product_id)
            if not product:
                raise NotFoundError(f"Product '{product_id}' is unavailable.")
            quantity = int(entry.get("quantity", 0))
            if quantity <= 0:
                raise ValidationError(f"Invalid quantity for {product['name']}.")
            if quantity > product["stock_quantity"]:
                raise ValidationError(f"Only {product['stock_quantity']} units remain for {product['name']}.")
        return self.calculate_total(conversation_id, shipping_fee=self.repository.store_policies.get("shipping", {}).get("shipping_fee", 50))
