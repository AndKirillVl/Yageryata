import pytest

from zup.compare import best_per_chain, run_search, sort_products, verdict
from zup.http import ParserError
from zup.models import City, Product, Store
from zup.parsers.base import StoreChainParser
from zup.parsers.demo import DemoParser


class BrokenParser(StoreChainParser):
    chain = "Магнит"

    def find_store(self, city: City) -> Store:
        raise ParserError("Магнит: доступ запрещён")

    def search(self, store, query, limit):  # pragma: no cover
        raise AssertionError


class CrashParser(BrokenParser):
    def find_store(self, city: City) -> Store:
        raise KeyError("boom")


def demo_parsers():
    return {"Пятёрочка": DemoParser("Пятёрочка"), "Магнит": DemoParser("Магнит")}


def test_search_finds_products_in_both_chains():
    result = run_search("молоко", "Пенза", demo_parsers(), 20, demo=True)
    chains = {p.chain for p in result.products}
    assert chains == {"Пятёрочка", "Магнит"}
    assert not result.errors
    assert all(p.is_demo for p in result.products)


def test_one_chain_failure_does_not_break_other():
    parsers = {"Пятёрочка": DemoParser("Пятёрочка"), "Магнит": BrokenParser()}
    result = run_search("хлеб", "Пенза", parsers, 20)
    assert {p.chain for p in result.products} == {"Пятёрочка"}
    assert "доступ запрещён" in result.errors["Магнит"]


def test_unexpected_exception_is_reported_not_raised():
    parsers = {"Магнит": CrashParser()}
    result = run_search("хлеб", "Пенза", parsers, 20)
    assert result.products == [] and "Магнит" in result.errors


def test_empty_query_and_unknown_city_rejected():
    with pytest.raises(ValueError):
        run_search("   ", "Пенза", demo_parsers(), 20)
    with pytest.raises(ValueError):
        run_search("молоко", "Москва", demo_parsers(), 20)


def test_store_is_cached_between_searches():
    calls = []

    class Counting(DemoParser):
        def find_store(self, city):
            calls.append(city.name)
            return super().find_store(city)

    cache = {}
    parsers = {"Пятёрочка": Counting("Пятёрочка")}
    run_search("молоко", "Пенза", parsers, 5, cache)
    run_search("хлеб", "Пенза", parsers, 5, cache)
    assert calls == ["Пенза"]


def test_sort_and_best_per_chain_use_unit_price():
    a = Product("Пятёрочка", "1", "Молоко 1л", 100.0, unit_price=100.0, unit_label="л")
    b = Product("Пятёрочка", "2", "Молоко 2л", 170.0, unit_price=85.0, unit_label="л")
    c = Product("Магнит", "3", "Молоко 1л", 90.0, unit_price=90.0, unit_label="л")
    assert [p.product_id for p in sort_products([a, b, c])] == ["2", "3", "1"]
    best = best_per_chain([a, b, c])
    assert best["Пятёрочка"].product_id == "2" and best["Магнит"].product_id == "3"
    assert verdict([a, b, c]).startswith("Выгоднее в «Пятёрочка»")


def test_verdict_single_chain_empty_and_equal():
    assert verdict([]) == "Ничего не найдено."
    only = Product("Магнит", "1", "Хлеб", 40.0)
    assert "только в сети «Магнит»" in verdict([only])
    same = [Product("Магнит", "1", "Хлеб", 40.0), Product("Пятёрочка", "2", "Хлеб", 40.0)]
    assert verdict(same).startswith("Цены одинаковы")


def test_out_of_stock_ignored_for_best_when_alternatives_exist():
    gone = Product("Магнит", "1", "Хлеб", 10.0, in_stock=False)
    here = Product("Магнит", "2", "Хлеб", 40.0)
    assert best_per_chain([gone, here])["Магнит"].product_id == "2"
