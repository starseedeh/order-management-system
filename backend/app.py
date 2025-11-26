from datetime import datetime, date
from io import BytesIO
import csv

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.database import init_db, db
from backend.models import (
    Commission,
    Customer,
    Order,
    OrderItem,
    PreorderStage,
    Product,
    User,
)


VAT_COUNTRIES = {"UK": 0.2, "United Kingdom": 0.2}
DEFAULT_COMMISSIONS = {"Ruby": 0.08, "Kirsty": 0.1}


def require_role(*allowed_roles):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            role = request.headers.get("X-Role", "sales")
            if allowed_roles and role not in allowed_roles:
                return jsonify({"error": "insufficient_permissions"}), 403
            return fn(*args, **kwargs)

        wrapper.__name__ = fn.__name__
        return wrapper

    return decorator


def create_app(testing: bool = False):
    app = Flask(__name__)
    if testing:
        app.config["TESTING"] = True
        database_url = "sqlite:///:memory:"
    else:
        database_url = None
    init_db(app, database_url=database_url)
    CORS(app)

    with app.app_context():
        seed_data()

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/dashboard")
    def dashboard():
        orders = Order.query.all()
        revenue = sum(o.total for o in orders)
        low_stock = Product.query.filter(Product.stock <= Product.safety_stock).count()
        preorder_orders = Order.query.filter(Order.status == "preorder").count()
        return jsonify(
            {
                "order_count": len(orders),
                "revenue": revenue,
                "low_stock": low_stock,
                "preorders": preorder_orders,
            }
        )

    @app.route("/api/customers", methods=["GET", "POST"])
    def customers():
        if request.method == "POST":
            data = request.json
            customer = Customer(
                name=data["name"],
                email=data["email"],
                phone=data.get("phone"),
                address=data.get("address"),
                locale=data.get("locale", "en"),
            )
            db.session.add(customer)
            db.session.commit()
            return jsonify(serialize_customer(customer)), 201
        all_customers = Customer.query.all()
        return jsonify([serialize_customer(c) for c in all_customers])

    @app.route("/api/products", methods=["GET", "POST"])
    def products():
        if request.method == "POST":
            data = request.json
            product = Product(
                name=data["name"],
                sku=data["sku"],
                base_price=data["base_price"],
                currency=data.get("currency", "USD"),
                stock=data.get("stock", 0),
                safety_stock=data.get("safety_stock", 0),
                preorder=data.get("preorder", False),
                early_bird_price=data.get("early_bird_price"),
                early_bird_end=parse_date(data.get("early_bird_end")),
            )
            for stage in data.get("preorder_stages", []):
                product.preorder_stages.append(
                    PreorderStage(
                        name=stage["name"],
                        price=stage["price"],
                        start_date=parse_date(stage["start_date"]),
                        end_date=parse_date(stage["end_date"]),
                    )
                )
            db.session.add(product)
            db.session.commit()
            return jsonify(serialize_product(product)), 201
        all_products = Product.query.order_by(Product.name).all()
        return jsonify([serialize_product(p) for p in all_products])

    @app.route("/api/products/<int:product_id>", methods=["PUT"])
    @require_role("admin")
    def update_product(product_id):
        product = Product.query.get_or_404(product_id)
        data = request.json
        product.name = data.get("name", product.name)
        product.stock = data.get("stock", product.stock)
        product.safety_stock = data.get("safety_stock", product.safety_stock)
        product.base_price = data.get("base_price", product.base_price)
        product.preorder = data.get("preorder", product.preorder)
        product.early_bird_price = data.get("early_bird_price", product.early_bird_price)
        product.early_bird_end = parse_date(data.get("early_bird_end")) or product.early_bird_end
        db.session.commit()
        return jsonify(serialize_product(product))

    @app.route("/api/products/export")
    @require_role("admin")
    def export_products():
        products = Product.query.all()
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(["name", "sku", "price", "stock", "safety_stock", "preorder"])
        for p in products:
            writer.writerow([p.name, p.sku, p.base_price, p.stock, p.safety_stock, p.preorder])
        output.seek(0)
        return send_file(
            output,
            mimetype="text/csv",
            as_attachment=True,
            download_name="products.csv",
        )

    @app.route("/api/products/import", methods=["POST"])
    @require_role("admin")
    def import_products():
        csv_text = request.get_data(as_text=True)
        if not csv_text:
            return jsonify({"error": "missing_csv"}), 400
        reader = csv.DictReader(csv_text.splitlines())
        imported = 0
        for row in reader:
            product = Product.query.filter_by(sku=row["sku"]).first()
            if not product:
                product = Product(sku=row["sku"])
            product.name = row["name"]
            product.base_price = float(row.get("price", 0))
            product.stock = int(row.get("stock", 0))
            product.safety_stock = int(row.get("safety_stock", 0))
            product.preorder = row.get("preorder", "false").lower() == "true"
            db.session.add(product)
            imported += 1
        db.session.commit()
        return jsonify({"imported": imported})

    @app.route("/api/orders", methods=["GET", "POST"])
    def orders():
        if request.method == "POST":
            data = request.json
            try:
                order = create_order_from_payload(data)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            return jsonify(serialize_order(order)), 201
        all_orders = Order.query.order_by(Order.created_at.desc()).all()
        return jsonify([serialize_order(o) for o in all_orders])

    @app.route("/api/orders/<int:order_id>", methods=["GET", "PUT", "DELETE"])
    def order_detail(order_id):
        order = Order.query.get_or_404(order_id)
        if request.method == "GET":
            return jsonify(serialize_order(order))

        if request.method == "PUT":
            data = request.json or {}
            try:
                update_order(order, data)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            return jsonify(serialize_order(order))

        # DELETE
        restock_items(order)
        db.session.delete(order)
        db.session.commit()
        return jsonify({"deleted": True})

    @app.route("/api/orders/<int:order_id>/fulfill", methods=["POST"])
    def fulfill_order(order_id):
        order = Order.query.get_or_404(order_id)
        order.status = "fulfilled"
        db.session.commit()
        return jsonify(serialize_order(order))

    @app.route("/api/orders/<int:order_id>/invoice/pdf")
    def invoice_pdf(order_id):
        order = Order.query.get_or_404(order_id)
        pdf_bytes = build_invoice_pdf(order)
        return send_file(pdf_bytes, download_name=f"order-{order_id}.pdf", mimetype="application/pdf", as_attachment=True)

    @app.route("/api/orders/<int:order_id>/invoice/excel")
    def invoice_excel(order_id):
        order = Order.query.get_or_404(order_id)
        excel_bytes = build_invoice_excel(order)
        return send_file(
            excel_bytes,
            download_name=f"order-{order_id}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
        )

    return app


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value).date()


def seed_data():
    if User.query.count() == 0:
        db.session.add_all(
            [User(name="Ruby", role="sales"), User(name="Kirsty", role="sales"), User(name="Admin", role="admin")]
        )
    if Customer.query.count() == 0:
        db.session.add_all(
            [
                Customer(name="Acme Ltd", email="info@acme.test", phone="12345", address="London, UK", locale="en"),
                Customer(name="宏大貿易", email="service@hongda.tw", phone="02-5555-0000", address="台北市", locale="zh-TW"),
            ]
        )
    if Product.query.count() == 0:
        lamp = Product(
            name="Smart Lamp",
            sku="LAMP-001",
            base_price=120,
            stock=25,
            safety_stock=5,
            preorder=False,
        )
        headset = Product(
            name="Studio Headset",
            sku="HS-009",
            base_price=180,
            stock=5,
            safety_stock=4,
            preorder=True,
            early_bird_price=150,
            early_bird_end=date.today(),
        )
        headset.preorder_stages.append(
            PreorderStage(
                name="Early Bird",
                price=150,
                start_date=date.today(),
                end_date=date.today(),
            )
        )
        db.session.add_all([lamp, headset])
    db.session.commit()


def serialize_customer(customer: Customer):
    return {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "address": customer.address,
        "locale": customer.locale,
    }


def serialize_product(product: Product):
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "base_price": product.base_price,
        "currency": product.currency,
        "stock": product.stock,
        "safety_stock": product.safety_stock,
        "preorder": product.preorder,
        "early_bird_price": product.early_bird_price,
        "early_bird_end": product.early_bird_end.isoformat() if product.early_bird_end else None,
        "preorder_stages": [
            {
                "name": stage.name,
                "price": stage.price,
                "start_date": stage.start_date.isoformat(),
                "end_date": stage.end_date.isoformat(),
            }
            for stage in product.preorder_stages
        ],
    }


def serialize_order(order: Order):
    return {
        "id": order.id,
        "customer": serialize_customer(order.customer),
        "sales_person": order.sales_person_id,
        "status": order.status,
        "country": order.country,
        "currency": order.currency,
        "shipping_courier": order.shipping_courier,
        "tracking_number": order.tracking_number,
        "total": order.total,
        "vat_amount": order.vat_amount,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "product": serialize_product(item.product),
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.subtotal,
            }
            for item in order.items
        ],
        "commission": serialize_commission(order.commission) if order.commission else None,
    }


def serialize_commission(commission: Commission):
    return {
        "rate": commission.rate,
        "amount": commission.amount,
        "sales_person": commission.user.name if commission.user else None,
    }


def create_order_from_payload(data):
    customer_id = data["customer_id"]
    country = data.get("country", "US")
    currency = data.get("currency", "USD")
    sales_person_id = data.get("sales_person_id")
    shipping_courier = data.get("shipping_courier")
    tracking_number = data.get("tracking_number")
    status = data.get("status", "confirmed")

    order = Order(
        customer_id=customer_id,
        status=status,
        country=country,
        currency=currency,
        sales_person_id=sales_person_id,
        shipping_courier=shipping_courier,
        tracking_number=tracking_number,
    )
    db.session.add(order)

    subtotal = 0
    for item_data in data.get("items", []):
        product = Product.query.get(item_data["product_id"])
        if not product:
            raise ValueError("Product not found")
        unit_price = item_data.get("unit_price") or product.active_price()
        quantity = item_data.get("quantity", 1)
        subtotal_line = unit_price * quantity
        subtotal += subtotal_line
        order.items.append(
            OrderItem(product_id=product.id, quantity=quantity, unit_price=unit_price, subtotal=subtotal_line)
        )
        if not product.preorder:
            product.stock = max(product.stock - quantity, 0)

    vat_rate = VAT_COUNTRIES.get(country, 0)
    vat_amount = subtotal * vat_rate
    total = subtotal + vat_amount
    order.vat_amount = round(vat_amount, 2)
    order.total = round(total, 2)

    if sales_person_id:
        user = User.query.get(sales_person_id)
        rate = DEFAULT_COMMISSIONS.get(user.name, 0.05) if user else 0.05
        commission_amount = total * rate
        order.commission = Commission(user_id=sales_person_id, rate=rate, amount=commission_amount)

    if status == "preorder":
        for item in order.items:
            product = Product.query.get(item.product_id)
            if product:
                product.stock = product.stock  # explicit to show no deduction

    db.session.commit()
    return order


def restock_items(order: Order):
    for item in order.items:
        product = Product.query.get(item.product_id)
        if product and not product.preorder:
            product.stock += item.quantity


def update_order(order: Order, data: dict):
    # restore inventory before recalculating when item list is provided
    if data.get("items"):
        restock_items(order)
        order.items.clear()

    order.status = data.get("status", order.status)
    order.country = data.get("country", order.country)
    order.currency = data.get("currency", order.currency)
    order.shipping_courier = data.get("shipping_courier", order.shipping_courier)
    order.tracking_number = data.get("tracking_number", order.tracking_number)
    order.sales_person_id = data.get("sales_person_id", order.sales_person_id)

    subtotal = 0
    if data.get("items"):
        for item_data in data.get("items", []):
            product = Product.query.get(item_data["product_id"])
            if not product:
                raise ValueError("Product not found")
            quantity = item_data.get("quantity", 1)
            unit_price = item_data.get("unit_price") or product.active_price()
            subtotal_line = unit_price * quantity
            subtotal += subtotal_line
            order.items.append(
                OrderItem(product_id=product.id, quantity=quantity, unit_price=unit_price, subtotal=subtotal_line)
            )
            if not product.preorder:
                product.stock = max(product.stock - quantity, 0)
    else:
        subtotal = sum(item.subtotal for item in order.items)

    vat_rate = VAT_COUNTRIES.get(order.country, 0)
    order.vat_amount = round(subtotal * vat_rate, 2)
    order.total = round(subtotal + order.vat_amount, 2)

    if order.sales_person_id:
        user = User.query.get(order.sales_person_id)
        rate = DEFAULT_COMMISSIONS.get(user.name, 0.05) if user else 0.05
        if order.commission:
            order.commission.rate = rate
            order.commission.amount = order.total * rate
            order.commission.user_id = order.sales_person_id
        else:
            order.commission = Commission(user_id=order.sales_person_id, rate=rate, amount=order.total * rate)

    db.session.commit()


def build_invoice_pdf(order: Order):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(50, 750, f"Order #{order.id}")
    c.drawString(50, 730, f"Customer: {order.customer.name}")
    c.drawString(50, 710, f"Total: {order.total} {order.currency}")
    y = 680
    for item in order.items:
        c.drawString(50, y, f"{item.product.name} x {item.quantity} @ {item.unit_price} = {item.subtotal}")
        y -= 20
    c.drawString(50, y - 20, f"VAT: {order.vat_amount}")
    c.save()
    buffer.seek(0)
    return buffer


def build_invoice_excel(order: Order):
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice"
    ws.append(["Order", order.id])
    ws.append(["Customer", order.customer.name])
    ws.append(["", ""])
    ws.append(["Product", "Qty", "Unit Price", "Subtotal"])
    for item in order.items:
        ws.append([item.product.name, item.quantity, item.unit_price, item.subtotal])
    ws.append(["VAT", "", "", order.vat_amount])
    ws.append(["Total", "", "", order.total])
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
