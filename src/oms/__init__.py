"""Order management system core package."""

from .entities import Customer, Product, OrderItem, Order, OrderStatus
from .inventory import Inventory
from .order_manager import OrderManager, OrderError

__all__ = [
    "Customer",
    "Product",
    "OrderItem",
    "Order",
    "OrderStatus",
    "Inventory",
    "OrderManager",
    "OrderError",
]
