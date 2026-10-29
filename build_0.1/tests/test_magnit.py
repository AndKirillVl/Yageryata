import json
from pathlib import Path

from zup.models import Store
from zup.parsers.magnit import parse_products, parse_store_candidates, product_url

FIX = Path(__file__).parent / "fixtures"
STORE = Store("Магнит", "222", "г Пенза, ул Попова, д 5")


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_store_candidates_only_magnit_owner():
    stores = parse_store_candidates(load("magnit_stores.json"))
    assert [s.code for s in stores] == ["111", "222"]


def test_store_candidates_garbage():
    assert parse_store_candidates({}) == []
    assert parse_store_candidates(None) == []


def test_parse_products_converts_kopecks():
    products = parse_products(load("magnit_search.json"), STORE)
    assert [p.product_id for p in products] == ["1000049786", "1000127183", "1899800733"]
    first = products[0]
    assert first.price == 124.99
    assert first.unit_label == "кг" and first.unit_price == round(124.99 / 0.95, 2)
    promo = products[1]
    assert promo.price == 224.99 and promo.old_price == 259.99
    assert products[2].in_stock is False


def test_product_url_contains_store_code():
    url = product_url("123", "222")
    assert url.startswith("https://magnit.ru/product/123?") and "shopCode=222" in url


def test_parse_products_garbage():
    assert parse_products({}, STORE) == []
    assert parse_products([], STORE) == []
