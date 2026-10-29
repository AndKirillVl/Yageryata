"""Демо-режим: вымышленные товары и цены для проверки интерфейса без интернета.

ВАЖНО: цены здесь придуманы и не отражают реальные цены магазинов.
"""

from __future__ import annotations

from ..models import City, Product, Store
from ..units import unit_price
from .base import StoreChainParser

# (название с размером, цена в «Пятёрочке», цена в «Магните»)
_CATALOG: list[tuple[str, float, float]] = [
    ("Молоко 3.2% 950г", 92.99, 89.99),
    ("Молоко 2.5% 930мл", 84.99, 86.49),
    ("Молоко 3.2% 2л", 169.99, 164.99),
    ("Кефир 2.5% 900г", 79.99, 82.99),
    ("Творог 5% 200г", 74.99, 69.99),
    ("Хлеб белый нарезной 400г", 44.99, 42.99),
    ("Хлеб ржаной 350г", 49.99, 52.99),
    ("Булочка с маком 80г", 29.99, 27.99),
    ("Яйца куриные С1 10шт", 119.99, 124.99),
    ("Гречка ядрица 800г", 109.99, 99.99),
    ("Рис круглозёрный 900г", 119.99, 124.99),
    ("Макароны спагетти 450г", 64.99, 59.99),
    ("Сахар-песок 1кг", 74.99, 79.99),
    ("Масло подсолнечное рафинированное 900мл", 134.99, 129.99),
    ("Масло сливочное 82.5% 180г", 189.99, 199.99),
    ("Сыр российский 50% 200г", 219.99, 209.99),
    ("Сосиски молочные 450г", 189.99, 179.99),
    ("Курица тушка охлаждённая 1кг", 229.99, 239.99),
    ("Картофель мытый 1кг", 49.99, 44.99),
    ("Яблоки Гала 1кг", 119.99, 129.99),
    ("Бананы 1кг", 99.99, 94.99),
    ("Чай чёрный 100 пакетиков", 199.99, 189.99),
    ("Кофе растворимый 190г", 389.99, 399.99),
    ("Энергетик Adrenaline 0.449л", 89.99, 84.99),
    ("Энергетик Flash Up 0.45л", 69.99, 74.99),
    ("Вода питьевая негазированная 1.5л", 39.99, 36.99),
]


class DemoParser(StoreChainParser):
    def __init__(self, chain: str) -> None:
        self.chain = chain
        self._column = 1 if chain == "Пятёрочка" else 2

    def find_store(self, city: City) -> Store:
        return Store(self.chain, "DEMO", f"Демо-магазин ({city.name})", city.lat, city.lon)

    def search(self, store: Store, query: str, limit: int) -> list[Product]:
        tokens = query.casefold().split()
        result: list[Product] = []
        for index, row in enumerate(_CATALOG):
            name, price = row[0], row[self._column]
            if not all(t in name.casefold() for t in tokens):
                continue
            up = unit_price(price, name)
            home = "https://5ka.ru/" if self.chain == "Пятёрочка" else "https://magnit.ru/"
            result.append(
                Product(
                    chain=self.chain,
                    product_id=f"demo-{index}",
                    name=name,
                    price=price,
                    unit_price=up[0] if up else None,
                    unit_label=up[1] if up else None,
                    url=home,
                    store_address=store.address,
                    is_demo=True,
                )
            )
        return result[:limit]
