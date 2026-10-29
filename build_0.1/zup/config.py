"""Настройки приложения и список городов Пензенской области."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import City

# Корень сборки (папка, где лежит main.py)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SETTINGS_PATH = BASE_DIR / "settings.json"

# Координаты центров городов — приблизительные, их достаточно для поиска
# ближайшего магазина. Список можно расширять.
CITIES: dict[str, City] = {
    c.name: c
    for c in (
        City("Пенза", 53.1950, 45.0183),
        City("Заречный", 53.2003, 45.1672),
        City("Кузнецк", 53.1131, 46.6053),
        City("Каменка", 53.1850, 44.0453),
        City("Нижний Ломов", 53.5333, 43.6728),
        City("Сердобск", 52.4658, 44.2036),
        City("Белинский", 52.9658, 43.4194),
        City("Никольск", 53.7142, 46.0783),
        City("Спасск", 53.9231, 43.1858),
        City("Городище", 53.2733, 45.7003),
    )
}
DEFAULT_CITY = "Пенза"

DEFAULT_SETTINGS: dict[str, Any] = {
    # Адрес прокси, например "http://user:pass@host:port" (пусто — без прокси)
    "proxy": "",
    # Строка Cookie из браузера, где открыт сайт 5ka.ru (нужна, если сайт отвечает 403)
    "pyaterochka_cookie": "",
    # Значения заголовков приложения Пятёрочки (при смене версии сайта поменять здесь)
    "pyaterochka_app_version": "8.45.0",
    "pyaterochka_platform": "web",
    "timeout_sec": 15,
    "results_per_store": 20,
    # Минимальная пауза между запросами к одному сайту, сек.
    "min_interval_sec": 0.5,
}


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    """Читает settings.json; недостающие ключи берутся из значений по умолчанию."""
    settings = dict(DEFAULT_SETTINGS)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Не удалось прочитать {path.name}: {exc}") from exc
        if isinstance(loaded, dict):
            settings.update({k: v for k, v in loaded.items() if k in DEFAULT_SETTINGS})
    return settings
