"""Парсер «Магнита». Использует API приложения (middle-api.magnit.ru), без входа в аккаунт.

Эндпоинты (проверены по открытым клиентам API, структура ответов может меняться):
  POST /v1/stores-facade/search   — магазины в радиусе от точки
  POST /v1/stores-facade/store    — карточка магазина (адрес)
  POST /v2/goods/search           — поиск товаров по тексту (term) в магазине
Цены в ответе — в копейках.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..http import HttpClient, ParserError
from ..models import City, Product, Store
from ..units import unit_price
from .base import StoreChainParser, distance_m

CHAIN = "Магнит"
API_URL = "https://middle-api.magnit.ru"
SITE_URL = "https://magnit.ru"
# Каталог «Магнит Экспресс» привязан к одному магазину
STORE_TYPE = "express"
CATALOG_TYPE = "2"
SEARCH_RADII_M = (3000, 10000, 30000)  # расширяем радиус для небольших городов


def parse_store_candidates(payload: Any) -> list[Store]:
    """Разбирает ответ /v1/stores-facade/search (адреса в нём нет)."""
    try:
        items = payload["items"]["items"]
    except (KeyError, TypeError):
        return []
    stores: list[Store] = []
    for raw in items if isinstance(items, list) else []:
        ext = raw.get("externalId") or {}
        if ext.get("owner") != "OWNER_MAGNIT" or not ext.get("storeCode"):
            continue
        coords = raw.get("coordinates") or {}
        stores.append(
            Store(
                chain=CHAIN,
                code=str(ext["storeCode"]),
                lat=coords.get("latitude"),
                lon=coords.get("longitude"),
            )
        )
    return stores


def product_url(product_id: str, store_code: str) -> str:
    return f"{SITE_URL}/product/{product_id}?shopCode={store_code}&shopType={STORE_TYPE}&catalogType={CATALOG_TYPE}"


def parse_products(payload: Any, store: Store) -> list[Product]:
    """Разбирает ответ /v2/goods/search."""
    items = payload.get("items") if isinstance(payload, dict) else None
    result: list[Product] = []
    for raw in items if isinstance(items, list) else []:
        name = str(raw.get("name") or "").strip()
        kopecks = raw.get("price")
        pid = str(raw.get("id") or "")
        if not name or not pid or not isinstance(kopecks, (int, float)) or kopecks <= 0:
            continue
        price = round(kopecks / 100, 2)
        promo = raw.get("promotion") or {}
        old_kopecks = promo.get("oldPrice")
        has_old = isinstance(old_kopecks, (int, float)) and old_kopecks > kopecks
        old_price = round(old_kopecks / 100, 2) if has_old else None
        up = unit_price(price, name)
        result.append(
            Product(
                chain=CHAIN,
                product_id=pid,
                name=name,
                price=price,
                old_price=old_price,
                unit_price=up[0] if up else None,
                unit_label=up[1] if up else None,
                url=product_url(pid, store.code),
                store_address=store.address,
                in_stock=not raw.get("isMissing", False),
            )
        )
    return result


class MagnitParser(StoreChainParser):
    chain = CHAIN

    def __init__(self, settings: dict[str, Any]) -> None:
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; SM-S918B Build/UP1A.231005.007)",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-app-version": "8.124.0",
            "x-device-id": str(uuid.uuid4()),
            "x-device-platform": "Android",
            "x-platform-version": "36",
        }
        self.http = HttpClient(
            CHAIN,
            headers,
            proxy=str(settings.get("proxy") or ""),
            timeout=float(settings["timeout_sec"]),
            min_interval=float(settings["min_interval_sec"]),
        )

    def _address(self, code: str) -> str:
        try:
            payload = self.http.request_json(
                "POST",
                f"{API_URL}/v1/stores-facade/store",
                json_body={"externalId": {"owner": "OWNER_MAGNIT", "storeCode": code}},
            )
            return str(payload.get("address") or "")
        except ParserError:
            return ""  # адрес нужен только для показа, поиск от него не зависит

    def find_store(self, city: City) -> Store:
        for radius in SEARCH_RADII_M:
            payload = self.http.request_json(
                "POST",
                f"{API_URL}/v1/stores-facade/search",
                json_body={
                    "filters": {
                        "geo": {
                            "typeName": "circle",
                            "coordinates": {"latitude": city.lat, "longitude": city.lon},
                            "distance_meters": radius,
                        },
                        "deliveryTypeList": ["DELIVERY_TYPE_DELIVERY"],
                    }
                },
            )
            stores = parse_store_candidates(payload)
            if stores:
                nearest = min(
                    stores,
                    key=lambda s: distance_m(city.lat, city.lon, s.lat, s.lon)
                    if s.lat is not None and s.lon is not None
                    else float("inf"),
                )
                return Store(CHAIN, nearest.code, self._address(nearest.code), nearest.lat, nearest.lon)
        raise ParserError(f"{CHAIN}: в городе {city.name} не найдено магазинов с каталогом.")

    def search(self, store: Store, query: str, limit: int) -> list[Product]:
        payload = self.http.request_json(
            "POST",
            f"{API_URL}/v2/goods/search",
            json_body={
                "storeType": STORE_TYPE,
                "catalogType": CATALOG_TYPE,
                "storeCode": store.code,
                "term": query,
                "pagination": {"limit": min(max(limit, 1), 50), "offset": 0},
                "sort": {"order": "desc", "type": "relevance"},
            },
        )
        return parse_products(payload, store)[:limit]
