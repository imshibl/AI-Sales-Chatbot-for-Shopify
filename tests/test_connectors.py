from __future__ import annotations

from types import SimpleNamespace

from app.repositories.catalogs import RESTProductCatalog, ShopifyProductCatalog, _normalize_product
from app.repositories.catalogs import SQLProductCatalog
from app.repositories.sqlalchemy_repository import SQLAlchemyRepository
from app.repositories.memory import MemoryRepository
from app.services.cart_service import CartService
from sqlalchemy import create_engine, text


def test_sql_repository_persists_conversations_and_orders(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'store.db'}"
    first = SQLAlchemyRepository(database_url)
    conversation = first.create_conversation({"conversation_id": "conv_test", "messages": [], "cart": {}})
    first.create_order({"id": "order_test", "customer_id": first.demo_customer_id, "payment_reference": "pay_test"})

    second = SQLAlchemyRepository(database_url)
    assert second.get_conversation("conv_test") == conversation
    assert second.get_order_by_payment_reference("pay_test")["id"] == "order_test"
    assert second.list_products()


def test_rest_catalog_normalizes_shop_products(monkeypatch):
    payload = {
        "products": [
            {
                "id": "sku-1",
                "name": "Hydrating Cream",
                "price": "12.50",
                "stock_quantity": 4,
                "benefits": ["hydrating"],
            }
        ]
    }

    def fake_get(*args, **kwargs):
        authorization = kwargs["headers"]["Authorization"]
        assert authorization.startswith("Bearer ")
        assert authorization[len("Bearer ") :] == "token"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: payload,
        )

    monkeypatch.setattr("app.repositories.catalogs.httpx.get", fake_get)
    catalog = RESTProductCatalog("https://store.example/products", "token", 0)
    assert catalog.list_products() == [
        _normalize_product(payload["products"][0])
    ]
    assert catalog.list_products()[0]["price"] == 12.5


def test_graphql_catalog_reads_connection_nodes(monkeypatch):
    product = {"id": "sku-2", "name": "Daily Moisturizer", "price": 25}

    def fake_post(*args, **kwargs):
        assert kwargs["json"] == {"query": "query { products { edges { node { id name price } } } }"}
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": {"products": {"edges": [{"node": product}]}}},
        )

    monkeypatch.setattr("app.repositories.catalogs.httpx.post", fake_post)
    catalog = RESTProductCatalog(
        "https://store.example/graphql",
        "",
        0,
        api_type="graphql",
        graphql_query="query { products { edges { node { id name price } } } }",
    )
    assert catalog.list_products()[0]["id"] == "sku-2"


def test_shopify_product_mapping_preserves_fractional_price():
    product = ShopifyProductCatalog._map_product(
        {
            "id": "gid://shopify/Product/12",
            "title": "Travel Bottle",
            "handle": "travel-bottle",
            "description": "Reusable bottle",
            "productType": "Accessories",
            "tags": ["travel"],
            "availableForSale": True,
            "featuredImage": {"url": "https://store.example/bottle.jpg"},
            "priceRange": {"minVariantPrice": {"amount": "19.95", "currencyCode": "USD"}},
        }
    )
    assert product["price"] == 19.95
    assert product["stock_quantity"] is None


def test_cart_allows_active_product_when_stock_count_is_unknown():
    repository = MemoryRepository()
    repository.products["sku-unknown-stock"] = _normalize_product(
        {"id": "sku-unknown-stock", "name": "Travel Bottle", "price": "19.95"}
    )
    repository.create_conversation({"conversation_id": "conv_unknown_stock", "cart": {}})

    cart = CartService(repository)
    assert cart.add_item("conv_unknown_stock", "sku-unknown-stock", quantity=2)["sku-unknown-stock"]["quantity"] == 2


def test_cart_totals_preserve_fractional_catalog_prices():
    repository = MemoryRepository()
    repository.products["sku-3"] = _normalize_product(
        {"id": "sku-3", "name": "Travel Bottle", "price": "19.95", "stock_quantity": 3}
    )
    repository.create_conversation({"conversation_id": "conv_decimal", "cart": {}})
    cart = CartService(repository)
    cart.add_item("conv_decimal", "sku-3")

    total = cart.calculate_total("conv_decimal")
    assert total["subtotal"] == 19.95
    assert total["total"] == 69.95


def test_sql_catalog_maps_operator_query_columns(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'catalog.db'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE inventory (sku TEXT, title TEXT, amount NUMERIC)"))
        connection.execute(
            text("INSERT INTO inventory (sku, title, amount) VALUES ('sku-4', 'Desk Lamp', 32.75)")
        )

    catalog = SQLProductCatalog(
        database_url,
        "SELECT sku AS id, title AS name, amount AS price FROM inventory",
        0,
    )
    product = catalog.list_products()[0]
    assert product["id"] == "sku-4"
    assert product["price"] == 32.75
