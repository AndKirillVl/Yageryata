"""Модели данных приложения."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    """Город Пензенской области (координаты центра нужны для поиска магазинов)."""

    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class Store:
    """Конкретный магазин сети, по которому берутся цены."""

    chain: str
    code: str
    address: str = ""
    lat: float | None = None
    lon: float | None = None


@dataclass
class Product:
    """Товар в одном магазине. Цены — в рублях."""

    chain: str
    product_id: str
    name: str
    price: float
    old_price: float | None = None
    unit_price: float | None = None  # цена за 1 кг или 1 л
    unit_label: str | None = None  # «кг» или «л»
    url: str = ""
    store_address: str = ""
    in_stock: bool = True
    is_demo: bool = False


@dataclass
class SearchResult:
    """Итог поиска по всем сетям: товары и ошибки по каждой сети отдельно."""

    query: str
    city: str
    products: list[Product]
    errors: dict[str, str]
    stores: dict[str, Store]
    demo: bool = False
