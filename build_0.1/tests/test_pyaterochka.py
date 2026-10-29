import json
from pathlib import Path

from zup.models import Store
from zup.parsers.pyaterochka import parse_products, parse_stores, product_prices

FIX = Path(__file__).parent / "fixtures"
STORE = Store("Пятёрочка", "S102", "г Пенза, ул Кирова, д 10")


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_parse_stores_skips_items_without_code():
    stores = parse_stores(load("pyaterochka_stores.json"))
    assert [s.code for s in stores] == ["S101", "S102"]
    assert stores[1].lat == 53.1951 and stores[1].address.startswith("г Пенза")


def test_product_prices_discount_and_regular():
    assert product_prices({"prices": {"regular": 120.0, "discount": 89.9}}) == (89.9, 120.0)
    assert product_prices({"prices": {"regular": 99.99}}) == (99.99, None)
    assert product_prices({"prices": {}}) == (None, None)


def test_parse_products():
    products = parse_products(load("pyaterochka_search.json"), STORE)
    assert [p.product_id for p in products] == ["100", "101", "102"]  # без цены и без названия — отброшены
    milk = products[0]
    assert milk.name == "Молоко Простоквашино, 930 мл"
    assert milk.price == 99.99
    assert milk.unit_label == "л" and milk.unit_price == round(99.99 / 0.93, 2)
    assert milk.url == "https://5ka.ru/product/100"
    promo = products[1]
    assert promo.price == 89.9 and promo.old_price == 120.0
    assert products[2].in_stock is False


def test_parse_products_garbage_payload():
    assert parse_products({"unexpected": 1}, STORE) == []
    assert parse_products(None, STORE) == []
