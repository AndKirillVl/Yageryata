"""Хранилище SQLite: избранные товары и выбранный город."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS favorites (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chain         TEXT NOT NULL,
    product_id    TEXT NOT NULL,
    city          TEXT NOT NULL,
    name          TEXT NOT NULL,
    price         REAL NOT NULL,
    old_price     REAL,
    unit_price    REAL,
    unit_label    TEXT,
    url           TEXT NOT NULL DEFAULT '',
    store_address TEXT NOT NULL DEFAULT '',
    saved_at      TEXT NOT NULL,
    UNIQUE (chain, product_id, city)
);
"""


@dataclass
class Favorite:
    id: int
    chain: str
    product_id: str
    city: str
    name: str
    price: float
    old_price: float | None
    unit_price: float | None
    unit_label: str | None
    url: str
    store_address: str
    saved_at: str


class Storage:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- настройки -----------------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    # --- избранное -----------------------------------------------------
    def add_favorite(self, product: Product, city: str) -> bool:
        """Сохраняет товар. Возвращает False, если он уже был в избранном (цена при этом обновляется)."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        exists = self.conn.execute(
            "SELECT 1 FROM favorites WHERE chain = ? AND product_id = ? AND city = ?",
            (product.chain, product.product_id, city),
        ).fetchone()
        self.conn.execute(
            """
            INSERT INTO favorites(chain, product_id, city, name, price, old_price, unit_price,
                                  unit_label, url, store_address, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chain, product_id, city) DO UPDATE SET
                name = excluded.name, price = excluded.price, old_price = excluded.old_price,
                unit_price = excluded.unit_price, unit_label = excluded.unit_label,
                url = excluded.url, store_address = excluded.store_address,
                saved_at = excluded.saved_at
            """,
            (
                product.chain, product.product_id, city, product.name, product.price,
                product.old_price, product.unit_price, product.unit_label, product.url,
                product.store_address, now,
            ),
        )
        self.conn.commit()
        return exists is None

    def list_favorites(self) -> list[Favorite]:
        rows = self.conn.execute("SELECT * FROM favorites ORDER BY saved_at DESC, id DESC").fetchall()
        return [Favorite(**dict(r)) for r in rows]

    def remove_favorite(self, favorite_id: int) -> None:
        self.conn.execute("DELETE FROM favorites WHERE id = ?", (favorite_id,))
        self.conn.commit()
