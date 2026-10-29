"""Поиск по всем сетям и сравнение цен."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from .config import CITIES
from .http import ParserError
from .models import Product, SearchResult, Store
from .parsers.base import StoreChainParser

log = logging.getLogger(__name__)

# Кэш выбранных магазинов: (сеть, город) -> Store. Нужен, чтобы не искать магазин при каждом поиске.
StoreCache = dict[tuple[str, str], Store]


def run_search(
    query: str,
    city_name: str,
    parsers: Mapping[str, StoreChainParser],
    limit: int,
    store_cache: StoreCache | None = None,
    demo: bool = False,
) -> SearchResult:
    """Ищет товар во всех сетях. Сбой одной сети не мешает показать результаты другой."""
    query = query.strip()
    if not query:
        raise ValueError("Введите название товара.")
    if city_name not in CITIES:
        raise ValueError(f"Неизвестный город: {city_name}")
    city = CITIES[city_name]
    cache = store_cache if store_cache is not None else {}

    products: list[Product] = []
    errors: dict[str, str] = {}
    stores: dict[str, Store] = {}
    for chain, parser in parsers.items():
        try:
            store = cache.get((chain, city_name))
            if store is None:
                store = parser.find_store(city)
                cache[(chain, city_name)] = store
            stores[chain] = store
            products.extend(parser.search(store, query, limit))
        except ParserError as exc:
            log.warning("%s: %s", chain, exc)
            errors[chain] = str(exc)
        except Exception as exc:  # noqa: BLE001 — непредвиденный формат ответа не должен ронять приложение
            log.exception("%s: непредвиденная ошибка при поиске «%s»", chain, query)
            errors[chain] = f"{chain}: неожиданная ошибка разбора ответа ({exc.__class__.__name__}: {exc})"
    return SearchResult(query, city_name, products, errors, stores, demo)


def sort_key(p: Product) -> tuple[float, float]:
    """Сортировка: сначала по цене за кг/л (если известна), затем по цене."""
    return (p.unit_price if p.unit_price is not None else float("inf"), p.price)


def sort_products(products: list[Product]) -> list[Product]:
    return sorted(products, key=sort_key)


def _best(items: list[Product]) -> Product | None:
    in_stock = [p for p in items if p.in_stock] or items
    if not in_stock:
        return None
    with_unit = [p for p in in_stock if p.unit_price is not None]
    if with_unit:
        return min(with_unit, key=lambda p: p.unit_price)  # type: ignore[arg-type,return-value]
    return min(in_stock, key=lambda p: p.price)


def best_per_chain(products: list[Product]) -> dict[str, Product]:
    """Самый выгодный товар каждой сети."""
    result: dict[str, Product] = {}
    for chain in dict.fromkeys(p.chain for p in products):
        best = _best([p for p in products if p.chain == chain])
        if best:
            result[chain] = best
    return result


def verdict(products: list[Product]) -> str:
    """Короткий вывод для пользователя: где выгоднее взять найденный товар."""
    best = best_per_chain(products)
    if not best:
        return "Ничего не найдено."
    if len(best) == 1:
        (chain, p), = best.items()
        return f"Найдено только в сети «{chain}»: {_describe(p)}"
    a, b = list(best.values())[:2]
    if a.unit_price is not None and b.unit_price is not None and a.unit_label == b.unit_label:
        cheaper, other = (a, b) if a.unit_price <= b.unit_price else (b, a)
        diff = other.unit_price - cheaper.unit_price  # type: ignore[operator]
        if diff < 0.005:
            return f"Цены одинаковы: {_describe(a)}; {_describe(b)}"
    else:
        cheaper, other = (a, b) if a.price <= b.price else (b, a)
        diff = other.price - cheaper.price
        if diff < 0.005:
            return f"Цены одинаковы: {_describe(a)}; {_describe(b)}"
    return f"Выгоднее в «{cheaper.chain}»: {_describe(cheaper)}. В «{other.chain}»: {_describe(other)}"


def _describe(p: Product) -> str:
    text = f"{p.name} — {p.price:.2f} ₽"
    if p.unit_price is not None:
        text += f" ({p.unit_price:.2f} ₽/{p.unit_label})"
    return text

