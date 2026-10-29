"""Парсер «Пятёрочки» (входит в X5 Клуб). Использует тот же API, что и сайт 5ka.ru.

Эндпоинты (проверены по открытым клиентам API, структура ответов может меняться):
  GET /cita/v1/stores/map              — магазины в прямоугольнике карты
  GET /catalog/v3/stores/{id}/search   — поиск товаров в магазине
Сайт защищён антиботом: без cookie из браузера запросы часто получают 403.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..http import HttpClient, ParserError
from ..models import City, Product, Store
from ..units import unit_price
from .base import StoreChainParser, distance_m

CHAIN = "Пятёрочка"
API_URL = "https://5d.5ka.ru/api"
SITE_URL = "https://5ka.ru"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _items(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def parse_stores(payload: Any) -> list[Store]:
    """Разбирает ответ /cita/v1/stores/map в список магазинов."""
    stores: list[Store] = []
    for raw in _items(payload, ("items", "stores", "results", "data")):
        code = raw.get("sapCode") or raw.get("sap_code") or raw.get("storeSapCode")
        if not code:
            continue
        pos = raw.get("coordinates") if isinstance(raw.get("coordinates"), dict) else raw
        address = raw.get("address") or raw.get("shop_address") or ""
        if isinstance(address, dict):
            address = address.get("formatted_address") or address.get("full") or ""
        stores.append(
            Store(
                chain=CHAIN,
                code=str(code),
                address=str(address),
                lat=_number(pos.get("latitude", pos.get("lat"))),
                lon=_number(pos.get("longitude", pos.get("lon"))),
            )
        )
    return stores


def product_prices(raw: dict[str, Any]) -> tuple[float | None, float | None]:
    """Возвращает (текущая цена, старая цена). Старая — только если она отличается."""
    prices = raw.get("prices") if isinstance(raw.get("prices"), dict) else {}
    regular = _number(prices.get("regular", prices.get("price")))
    current = (
        _number(prices.get("discount"))
        or _number(prices.get("cpd_promo_price"))
        or _number(prices.get("markdown"))
        or regular
        or _number(raw.get("price"))
    )
    old = regular if regular is not None and current is not None and regular != current else None
    return current, old


def parse_products(payload: Any, store: Store) -> list[Product]:
    """Разбирает ответ поиска /catalog/v3/stores/{id}/search."""
    result: list[Product] = []
    for raw in _items(payload, ("products", "items", "results", "data")):
        price, old_price = product_prices(raw)
        name = str(raw.get("name") or raw.get("title") or "").strip()
        plu = str(raw.get("plu") or raw.get("id") or "")
        if not name or price is None or price <= 0:
            continue
        size = str(raw.get("property_clarification") or raw.get("size") or "")
        up = unit_price(price, name, size)
        full_name = name if not size or size.lower() in name.lower() else f"{name}, {size}"
        available = raw.get("is_available")
        result.append(
            Product(
                chain=CHAIN,
                product_id=plu,
                name=full_name,
                price=round(price, 2),
                old_price=round(old_price, 2) if old_price else None,
                unit_price=up[0] if up else None,
                unit_label=up[1] if up else None,
                url=f"{SITE_URL}/product/{plu}" if plu else SITE_URL,
                store_address=store.address,
                in_stock=bool(available) if isinstance(available, bool) else True,
            )
        )
    return result


class PyaterochkaParser(StoreChainParser):
    chain = CHAIN

    def __init__(self, settings: dict[str, Any]) -> None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9",
            "Origin": SITE_URL,
            "Referer": f"{SITE_URL}/",
            "X-APP-VERSION": str(settings["pyaterochka_app_version"]),
            "X-PLATFORM": str(settings["pyaterochka_platform"]),
            "X-DEVICE-ID": str(uuid.uuid4()),
            "format": "json",
        }
        cookie = str(settings.get("pyaterochka_cookie") or "").strip()
        if cookie:
            headers["Cookie"] = cookie
        self.http = HttpClient(
            CHAIN,
            headers,
            proxy=str(settings.get("proxy") or ""),
            timeout=float(settings["timeout_sec"]),
            min_interval=float(settings["min_interval_sec"]),
        )

    def find_store(self, city: City) -> Store:
        for scale in (1, 3):  # сначала центр города, потом область шире
            payload = self.http.request_json(
                "GET",
                f"{API_URL}/cita/v1/stores/map",
                params={
                    "top_latitude": city.lat + 0.015 * scale,
                    "bottom_latitude": city.lat - 0.015 * scale,
                    "left_longitude": city.lon - 0.022 * scale,
                    "right_longitude": city.lon + 0.022 * scale,
                    "utm_referrer": f"{SITE_URL}/",
                },
            )
            stores = parse_stores(payload)
            if stores:
                return min(
                    stores,
                    key=lambda s: distance_m(city.lat, city.lon, s.lat, s.lon)
                    if s.lat is not None and s.lon is not None
                    else float("inf"),
                )
        raise ParserError(f"{CHAIN}: в городе {city.name} не найдено магазинов.")

    def search(self, store: Store, query: str, limit: int) -> list[Product]:
        payload = self.http.request_json(
            "GET",
            f"{API_URL}/catalog/v3/stores/{store.code}/search",
            params={
                "q": query,
                "mode": "store",
                "offset": 0,
                "limit": min(max(limit, 1), 50),
                "include_restrict": "true",
                "utm_referrer": f"{SITE_URL}/",
            },
        )
        return parse_products(payload, store)[:limit]
