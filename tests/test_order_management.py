from backend.database import db
from backend.models import Customer, Product


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_create_customer(client):
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "123",
        "address": "Somewhere",
        "locale": "en",
    }
    res = client.post("/api/customers", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["name"] == payload["name"]


def test_create_product_and_order_with_vat(client, app):
    product_payload = {
        "name": "Laptop",
        "sku": "LAP-001",
        "base_price": 1000,
        "stock": 4,
        "safety_stock": 1,
    }
    pres = client.post("/api/products", json=product_payload)
    assert pres.status_code == 201
    product_id = pres.get_json()["id"]

    customer = Customer.query.first()

    order_payload = {
        "customer_id": customer.id,
        "country": "UK",
        "items": [{"product_id": product_id, "quantity": 2}],
    }
    ores = client.post("/api/orders", json=order_payload)
    assert ores.status_code == 201
    order = ores.get_json()
    assert order["vat_amount"] == 400.0  # 20% VAT on 2000
    assert order["total"] == 2400.0

    with app.app_context():
        product = Product.query.get(product_id)
        assert product.stock == 2


def test_dashboard_counts(client):
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.get_json()
    assert "order_count" in data
    assert "low_stock" in data
