"""Точка входа: python main.py [--demo] [--city Пенза] [--query молоко]"""

from __future__ import annotations

import argparse
import logging
import sys

from zup import APP_NAME, __version__
from zup.config import DATA_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{__version__}")
    parser.add_argument("--demo", action="store_true", help="демо-режим (вымышленные цены, без интернета)")
    parser.add_argument("--city", help="город Пензенской области, например «Пенза»")
    parser.add_argument("--query", help="сразу выполнить поиск этого товара")
    args = parser.parse_args(argv)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=DATA_DIR / "zup.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )

    try:
        from zup.gui import run
    except ImportError as exc:  # на Linux tkinter ставится отдельно
        print(f"Не удалось запустить окно (нужен tkinter): {exc}", file=sys.stderr)
        return 1
    run(demo=True if args.demo else None, city=args.city, query=args.query)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
