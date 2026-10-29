"""Сквозная проверка парсеров с подменённым HTTP-слоем (без интернета)."""

import json
from pathlib import Path

import pytest

from zup.config import CITIES, DEFAULT_SETTINGS
from zup.http import ParserError
from zup.parsers.magnit import MagnitParser
from zup.parsers.pyaterochka import PyaterochkaParser

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_pyaterochka_flow(monkeypatch):
    parser = PyaterochkaParser(dict(DEFAULT_SETTINGS))
    calls = []

    def fake(method, url, **kw):
        calls.append((method, url, kw.get("params")))
        return load("pyaterochka_stores.json") if "stores/map" in url else load("pyaterochka_search.json")

    monkeypatch.setattr(parser.http, "request_json", fake)
    store = parser.find_store(CITIES["Пенза"])
    assert store.code == "S102"  # ближайший к центру Пензы
    products = parser.search(store, "молоко", 2)
    assert len(products) == 2
    assert calls[1][1].endswith("/catalog/v3/stores/S102/search")
    assert calls[1][2]["q"] == "молоко"


def test_pyaterochka_no_stores_raises(monkeypatch):
    parser = PyaterochkaParser(dict(DEFAULT_SETTINGS))
    monkeypatch.setattr(parser.http, "request_json", lambda *a, **k: {"stores": []})
    with pytest.raises(ParserError, match="не найдено магазинов"):
        parser.find_store(CITIES["Сердобск"])


def test_pyaterochka_cookie_and_proxy_from_settings():
    s = dict(DEFAULT_SETTINGS, pyaterochka_cookie="a=b", proxy="http://p:1")
    parser = PyaterochkaParser(s)
    assert parser.http.session.headers["Cookie"] == "a=b"
    assert parser.http.session.proxies["https"] == "http://p:1"


def test_magnit_flow(monkeypatch):
    parser = MagnitParser(dict(DEFAULT_SETTINGS))
    seen = []

    def fake(method, url, **kw):
        seen.append((url, kw.get("json_body")))
        if url.endswith("/stores-facade/search"):
            return load("magnit_stores.json")
        if url.endswith("/stores-facade/store"):
            return {"address": "г Пенза, ул Попова, д 5"}
        return load("magnit_search.json")

    monkeypatch.setattr(parser.http, "request_json", fake)
    store = parser.find_store(CITIES["Пенза"])
    assert store.code == "222" and store.address.startswith("г Пенза")
    products = parser.search(store, "молоко", 20)
    assert len(products) == 3
    assert seen[-1][1]["term"] == "молоко" and seen[-1][1]["storeCode"] == "222"


def test_magnit_radius_expands(monkeypatch):
    parser = MagnitParser(dict(DEFAULT_SETTINGS))
    radii = []

    def fake(method, url, **kw):
        if url.endswith("/stores-facade/search"):
            radii.append(kw["json_body"]["filters"]["geo"]["distance_meters"])
            return {"items": {"items": []}} if len(radii) < 3 else load("magnit_stores.json")
        return {"address": ""}

    monkeypatch.setattr(parser.http, "request_json", fake)
    parser.find_store(CITIES["Никольск"])
    assert radii == [3000, 10000, 30000]
