from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_public_store_config_exposes_brand_and_currency_only():
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    assert response.json() == {
        "store_name": "Thai Naturals",
        "currency": "INR",
        "is_demo_catalog": True,
    }


def test_product_listing_and_search():
    list_response = client.get("/api/v1/products")
    assert list_response.status_code == 200
    products = list_response.json()["products"]
    assert len(products) >= 10

    search_response = client.get("/api/v1/products/search", params={"q": "oily", "max_price": 1000})
    assert search_response.status_code == 200
    result = search_response.json()["products"]
    assert isinstance(result, list)


def test_chat_recommendations_use_catalog_filters():
    response = client.post(
        "/api/v1/chat",
        json={"message": "I have oily skin and acne marks, under ₹1,000"},
    )
    assert response.status_code == 200
    cards = response.json()["product_cards"]
    assert cards
    assert all(card["price"] <= 1000 for card in cards)
    assert "prod_001" in {card["id"] for card in cards}


def test_chat_rejects_unsupported_language():
    response = client.post("/api/v1/chat", json={"message": "Hello", "language": "fr"})
    assert response.status_code == 422


def test_chat_creates_conversation_and_cart_flow():
    chat_response = client.post("/api/v1/chat", json={"message": "Hi"})
    assert chat_response.status_code == 200
    payload = chat_response.json()
    conversation_id = payload["conversation_id"]
    assert conversation_id
    assert "Welcome" in payload["response"] or "Hi there" in payload["response"]

    history_response = client.get(f"/api/v1/chat/{conversation_id}/history")
    assert history_response.status_code == 200
    assert [message["role"] for message in history_response.json()["messages"]] == ["user", "assistant"]

    add_response = client.post(f"/api/v1/cart/{conversation_id}/items", json={"product_id": "prod_001", "quantity": 1})
    assert add_response.status_code == 200
    cart_payload = add_response.json()["cart"]
    assert cart_payload["prod_001"]["quantity"] == 1

    preview_response = client.post("/api/v1/orders/preview", json={"conversation_id": conversation_id})
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["total"] > 0

    order_response = client.post(
        "/api/v1/orders",
        json={
            "conversation_id": conversation_id,
            "customer_name": "Demo Customer",
            "email": "customer@example.com",
            "phone": "+91 98765 43210",
            "shipping_address": "12 Lotus Avenue, Bengaluru, Karnataka 560001",
            "confirmed": True,
        },
    )
    assert order_response.status_code == 200
    order = order_response.json()
    assert order["payment_url"]
    assert order["id"].startswith("TN-")
    assert order["payment_url"] == f"/payment/{order['payment_reference']}"
    assert client.get(f"/api/v1/cart/{conversation_id}").json()["cart"] == {}
    assert client.get("/api/v1/orders").json()["active_orders"][0]["id"] == order["id"]
    assert client.get(f"/api/v1/orders/{order['id']}/payment-status").json()["payment_status"] == "pending"
    demo_payment = client.get(f"/api/v1/demo/payments/{order['payment_reference']}")
    assert demo_payment.status_code == 200
    assert demo_payment.json()["payment_status"] == "pending"

    tracking_response = client.get(f"/api/v1/orders/{order['id']}/tracking")
    assert tracking_response.status_code == 200
    track = tracking_response.json()
    assert track["status"] == "pending_payment"
    assert track["tracking_url"] is None

    failed_payment = client.post(
        f"/api/v1/demo/payments/{order['id']}/complete",
        json={"outcome": "failed"},
    )
    assert failed_payment.status_code == 200
    assert failed_payment.json()["payment_status"] == "failed"
    assert client.get(f"/api/v1/orders/{order['id']}/payment-status").json()["order_status"] == "payment_failed"
    retry_payment = client.post(
        f"/api/v1/demo/payments/{order['id']}/complete",
        json={"outcome": "pending"},
    )
    assert retry_payment.json()["payment_status"] == "pending"

    payment_response = client.post(f"/api/v1/demo/payments/{order['id']}/complete", json={"outcome": "paid"})
    assert payment_response.status_code == 200
    assert payment_response.json()["payment_status"] == "paid"
    assert client.get(f"/api/v1/orders/{order['id']}/tracking").json()["tracking_url"]
    verified = client.get(f"/api/v1/orders/{order['id']}/payment-status")
    assert verified.json() == {
        "order_id": order["id"],
        "payment_status": "paid",
        "order_status": "confirmed",
    }
    assert order["id"] in {item["id"] for item in client.get("/api/v1/orders").json()["order_history"]}
