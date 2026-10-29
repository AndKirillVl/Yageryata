import pytest

from zup.units import parse_amount, unit_price


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Молоко 3.2% 950г", (0.95, "кг")),
        ("Молоко 930мл", (0.93, "л")),
        ("Вода 1,5л", (1.5, "л")),
        ("Сахар 1кг", (1.0, "кг")),
        ("Йогурт 125 гр", (0.125, "кг")),
        ("Сырки 2х150г", (0.3, "кг")),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["Яйца 10шт", "Булочка", "", "Хлеб 3.2%"])
def test_parse_amount_none(text):
    assert parse_amount(text) is None


def test_unit_price_per_kg_and_liter():
    assert unit_price(95.0, "Молоко 950г") == (100.0, "кг")
    assert unit_price(46.5, "Молоко", "930 мл") == (50.0, "л")


def test_unit_price_unknown_or_bad_price():
    assert unit_price(100, "Яйца 10шт") is None
    assert unit_price(0, "Молоко 1л") is None
