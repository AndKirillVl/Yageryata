"""Цена за килограмм / литр — чтобы честно сравнивать упаковки разного размера."""

from __future__ import annotations

import re

_AMOUNT_RE = re.compile(
    r"(?:(?P<mult>\d+)\s*[xх×]\s*)?"  # множитель: 2х150г
    r"(?P<num>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>кг|гр|г|мл|л)(?![а-яёa-z])",
    re.IGNORECASE,
)

# единица -> (базовая единица, делитель)
_TO_BASE = {"г": ("кг", 1000), "гр": ("кг", 1000), "кг": ("кг", 1), "мл": ("л", 1000), "л": ("л", 1)}


def parse_amount(*texts: str | None) -> tuple[float, str] | None:
    """Находит в тексте массу/объём и возвращает (количество, «кг»|«л»).

    Берётся последнее совпадение: размер упаковки обычно стоит в конце названия.
    """
    text = " ".join(t for t in texts if t)
    matches = list(_AMOUNT_RE.finditer(text))
    if not matches:
        return None
    m = matches[-1]
    num = float(m.group("num").replace(",", "."))
    mult = int(m.group("mult")) if m.group("mult") else 1
    base, divisor = _TO_BASE[m.group("unit").lower()]
    amount = num * mult / divisor
    if amount <= 0:
        return None
    return amount, base


def unit_price(price: float, *texts: str | None) -> tuple[float, str] | None:
    """Возвращает (цена за кг/л, «кг»|«л») или None, если размер не указан."""
    parsed = parse_amount(*texts)
    if parsed is None or price <= 0:
        return None
    amount, base = parsed
    return round(price / amount, 2), base
