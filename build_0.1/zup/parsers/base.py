"""Общий интерфейс парсера сети магазинов."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from ..models import City, Product, Store


class StoreChainParser(ABC):
    """Парсер одной сети. Работает в два шага: найти магазин в городе → найти товары."""

    chain: str = ""

    @abstractmethod
    def find_store(self, city: City) -> Store:
        """Возвращает ближайший к центру города магазин сети."""

    @abstractmethod
    def search(self, store: Store, query: str, limit: int) -> list[Product]:
        """Ищет товары по тексту запроса в выбранном магазине."""


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между точками в метрах (формула гаверсинусов)."""
    r = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
