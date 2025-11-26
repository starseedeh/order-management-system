"""Order management orchestrator handling lifecycle and validation."""

from __future__ import annotations

from typing import Dict, Iterable, List

from .entities import Customer, Order, OrderItem, OrderStatus
from .inventory import Inventory


class OrderError(Exception):
    """Raised when invalid order operations are attempted."""


class OrderManager:
    """Manages order creation and lifecycle using an inventory backend."""

    def __init__(self, inventory: Inventory):
        self.inventory = inventory
        self._orders: Dict[str, Order] = {}

    def create_order(self, order_id: str, customer: Customer, items: Iterable[OrderItem]) -> Order:
        if order_id in self._orders:
            raise OrderError(f"Order with id {order_id} already exists")

        order_items = list(items)
        if not order_items:
            raise OrderError("Cannot create an order without items")

        for item in order_items:
            self.inventory.reserve_stock(item.product.sku, item.quantity)

        order = Order(id=order_id, customer=customer, items=order_items)
        self._orders[order_id] = order
        return order

    def add_items(self, order_id: str, new_items: Iterable[OrderItem]) -> Order:
        order = self._get_order_or_raise(order_id)
        if order.status is not OrderStatus.PENDING:
            raise OrderError("Only pending orders can be modified")

        items_to_add = list(new_items)
        if not items_to_add:
            raise OrderError("No items provided to add")

        for item in items_to_add:
            self.inventory.reserve_stock(item.product.sku, item.quantity)

        order.extend_items(items_to_add)
        return order

    def cancel_order(self, order_id: str) -> Order:
        order = self._get_order_or_raise(order_id)
        if order.status is OrderStatus.CANCELLED:
            return order

        if order.status is OrderStatus.FULFILLED:
            raise OrderError("Fulfilled orders cannot be cancelled")

        for item in order.items:
            self.inventory.release_stock(item.product.sku, item.quantity)

        order.mark_cancelled()
        return order

    def fulfill_order(self, order_id: str) -> Order:
        order = self._get_order_or_raise(order_id)
        if order.status is OrderStatus.CANCELLED:
            raise OrderError("Cancelled orders cannot be fulfilled")
        order.mark_fulfilled()
        return order

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def list_orders(self) -> List[Order]:
        return list(self._orders.values())

    def _get_order_or_raise(self, order_id: str) -> Order:
        order = self.get_order(order_id)
        if not order:
            raise OrderError(f"Order {order_id} does not exist")
        return order
