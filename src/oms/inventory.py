"""Inventory tracking for product stock availability."""

from __future__ import annotations

from typing import Dict

from .entities import Product


class Inventory:
    """Simple inventory that tracks quantities available per product."""

    def __init__(self) -> None:
        self._stock: Dict[str, int] = {}
        self._products: Dict[str, Product] = {}

    def register_product(self, product: Product, quantity: int = 0) -> None:
        if quantity < 0:
            raise ValueError("Initial quantity cannot be negative")
        self._products[product.sku] = product
        self._stock.setdefault(product.sku, 0)
        self._stock[product.sku] += quantity

    def add_stock(self, sku: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Quantity to add cannot be negative")
        self._ensure_sku_exists(sku)
        self._stock[sku] += quantity

    def reserve_stock(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity to reserve must be greater than zero")
        self._ensure_sku_exists(sku)
        if self._stock[sku] < quantity:
            raise ValueError(f"Insufficient stock for SKU {sku}")
        self._stock[sku] -= quantity

    def release_stock(self, sku: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Quantity to release must be greater than zero")
        self._ensure_sku_exists(sku)
        self._stock[sku] += quantity

    def get_product(self, sku: str) -> Product:
        self._ensure_sku_exists(sku)
        return self._products[sku]

    def get_available_quantity(self, sku: str) -> int:
        self._ensure_sku_exists(sku)
        return self._stock[sku]

    def _ensure_sku_exists(self, sku: str) -> None:
        if sku not in self._products:
            raise KeyError(f"Product with SKU {sku} is not registered")
