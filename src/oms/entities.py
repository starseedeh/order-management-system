"""Core entities for the order management system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List


class OrderStatus(str, Enum):
    """Enumeration of supported order statuses."""

    PENDING = "pending"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Product:
    """Represents a purchasable product."""

    sku: str
    name: str
    price: float

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("Product price cannot be negative")


@dataclass(frozen=True)
class Customer:
    """Represents a customer who can place orders."""

    id: str
    name: str
    email: str

    def __post_init__(self) -> None:
        if "@" not in self.email:
            raise ValueError("Customer email must contain '@'")


@dataclass(frozen=True)
class OrderItem:
    """Represents a product entry within an order."""

    product: Product
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Order item quantity must be greater than zero")

    @property
    def total(self) -> float:
        return self.quantity * self.product.price


@dataclass
class Order:
    """Represents an order with status transitions and totals."""

    id: str
    customer: Customer
    items: List[OrderItem]
    status: OrderStatus = OrderStatus.PENDING
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("Order must contain at least one item")

    @property
    def total(self) -> float:
        return sum(item.total for item in self.items)

    def mark_fulfilled(self) -> None:
        self.status = OrderStatus.FULFILLED

    def mark_cancelled(self) -> None:
        self.status = OrderStatus.CANCELLED

    def add_metadata(self, key: str, value: str) -> None:
        self.metadata[key] = value

    def extend_items(self, new_items: Iterable[OrderItem]) -> None:
        self.items.extend(new_items)
