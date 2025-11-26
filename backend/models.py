from datetime import datetime, date
from sqlalchemy import CheckConstraint
from backend.database import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="sales")

    commissions = db.relationship("Commission", back_populates="user", cascade="all, delete-orphan")


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    address = db.Column(db.String(255))
    locale = db.Column(db.String(10), default="en")

    orders = db.relationship("Order", back_populates="customer", cascade="all, delete-orphan")


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(60), unique=True, nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(8), default="USD")
    stock = db.Column(db.Integer, nullable=False, default=0)
    safety_stock = db.Column(db.Integer, nullable=False, default=0)
    preorder = db.Column(db.Boolean, default=False)
    early_bird_price = db.Column(db.Float)
    early_bird_end = db.Column(db.Date)

    order_items = db.relationship("OrderItem", back_populates="product")
    preorder_stages = db.relationship("PreorderStage", back_populates="product", cascade="all, delete-orphan")

    def active_price(self, today=None):
        today = today or date.today()
        for stage in sorted(self.preorder_stages, key=lambda s: s.start_date):
            if stage.start_date <= today <= stage.end_date:
                return stage.price
        if self.preorder and self.early_bird_price and self.early_bird_end:
            if today <= self.early_bird_end:
                return self.early_bird_price
        return self.base_price


class PreorderStage(db.Model):
    __tablename__ = "preorder_stages"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    __table_args__ = (
        CheckConstraint("price >= 0"),
        CheckConstraint("end_date >= start_date"),
    )

    product = db.relationship("Product", back_populates="preorder_stages")


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    sales_person_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(30), nullable=False, default="draft")
    country = db.Column(db.String(60), default="US")
    currency = db.Column(db.String(8), default="USD")
    shipping_courier = db.Column(db.String(120))
    tracking_number = db.Column(db.String(120))
    total = db.Column(db.Float, nullable=False, default=0)
    vat_amount = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Customer", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    commission = db.relationship("Commission", uselist=False, back_populates="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class Commission(db.Model):
    __tablename__ = "commissions"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)

    order = db.relationship("Order", back_populates="commission")
    user = db.relationship("User", back_populates="commissions")
