"""Окно приложения (Tkinter): выбор города, поиск, сравнение цен, избранное."""

from __future__ import annotations

import dataclasses
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk
from typing import Any

from . import APP_NAME, __version__
from .compare import StoreCache, best_per_chain, run_search, sort_products, verdict
from .config import CITIES, DATA_DIR, DEFAULT_CITY, DEFAULT_SETTINGS, load_settings
from .models import Product, SearchResult
from .parsers.base import StoreChainParser
from .parsers.demo import DemoParser
from .parsers.magnit import MagnitParser
from .parsers.pyaterochka import PyaterochkaParser
from .storage import Storage

CHAINS = ("Пятёрочка", "Магнит")


def build_parsers(settings: dict[str, Any], demo: bool) -> dict[str, StoreChainParser]:
    """Создаёт парсеры сетей: настоящие или демонстрационные."""
    if demo:
        return {chain: DemoParser(chain) for chain in CHAINS}
    return {"Пятёрочка": PyaterochkaParser(settings), "Магнит": MagnitParser(settings)}


class App(tk.Tk):
    def __init__(
        self,
        *,
        demo: bool | None = None,
        city: str | None = None,
        query: str | None = None,
        db_path: str | None = None,
    ) -> None:
        super().__init__()
        self.title(f"{APP_NAME} — v{__version__}")
        self.geometry("1020x660")
        self.minsize(820, 520)

        self.storage = Storage(db_path or DATA_DIR / "zup.db")
        try:
            self.settings = load_settings()
        except ValueError as exc:
            messagebox.showerror(APP_NAME, f"{exc}\nБудут использованы настройки по умолчанию.")
            self.settings = dict(DEFAULT_SETTINGS)
        self._store_cache: StoreCache = {}
        self._fav_urls: dict[str, str] = {}
        self._parsers: dict[bool, dict[str, StoreChainParser]] = {}
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._results: dict[str, Product] = {}
        self._fav_ids: dict[str, int] = {}
        self._busy = False

        saved_city = self.storage.get_setting("city", DEFAULT_CITY)
        start_city = city if city in CITIES else (saved_city if saved_city in CITIES else DEFAULT_CITY)
        start_demo = demo if demo is not None else self.storage.get_setting("demo", "0") == "1"
        self.city_var = tk.StringVar(value=start_city)
        self.query_var = tk.StringVar(value=query or "")
        self.demo_var = tk.BooleanVar(value=start_demo)

        self._build_ui()
        self._refresh_favorites()
        self._update_demo_banner()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_queue)
        if query:
            self.after(300, self._start_search)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=26)
        style.configure("Header.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Verdict.TLabel", font=("Segoe UI", 11, "bold"))

        top = ttk.Frame(self, padding=(12, 10, 12, 4))
        top.pack(fill="x")
        ttk.Label(top, text=APP_NAME, style="Header.TLabel").grid(row=0, column=0, columnspan=6, sticky="w")
        ttk.Label(top, text="Город:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.city_box = ttk.Combobox(
            top, textvariable=self.city_var, values=list(CITIES), state="readonly", width=16
        )
        self.city_box.grid(row=1, column=1, sticky="w", padx=(4, 14), pady=(8, 0))
        self.city_box.bind("<<ComboboxSelected>>", self._on_city_change)
        ttk.Label(top, text="Товар:").grid(row=1, column=2, sticky="w", pady=(8, 0))
        entry = ttk.Entry(top, textvariable=self.query_var, width=34)
        entry.grid(row=1, column=3, sticky="we", padx=(4, 8), pady=(8, 0))
        entry.bind("<Return>", lambda _e: self._start_search())
        entry.focus_set()
        self.search_btn = ttk.Button(top, text="Найти", command=self._start_search)
        self.search_btn.grid(row=1, column=4, padx=(0, 14), pady=(8, 0))
        ttk.Checkbutton(
            top, text="Демо-режим", variable=self.demo_var, command=self._on_demo_toggle
        ).grid(row=1, column=5, pady=(8, 0))
        top.columnconfigure(3, weight=1)

        self.banner = ttk.Label(self, text="", foreground="#b00020", padding=(12, 0))
        self.banner.pack(fill="x")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(6, 0))

        # --- вкладка «Сравнение цен»
        tab_search = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab_search, text="Сравнение цен")
        self.verdict_var = tk.StringVar(value="Введите название товара и нажмите «Найти».")
        ttk.Label(
            tab_search, textvariable=self.verdict_var, style="Verdict.TLabel", wraplength=940, justify="left"
        ).pack(fill="x", pady=(0, 6))

        cols = ("chain", "name", "price", "old", "unit", "stock")
        self.tree = ttk.Treeview(tab_search, columns=cols, show="headings", selectmode="browse")
        for col, title, width, anchor in (
            ("chain", "Магазин", 100, "w"),
            ("name", "Товар", 440, "w"),
            ("price", "Цена, ₽", 90, "e"),
            ("old", "Без скидки, ₽", 100, "e"),
            ("unit", "За кг / л, ₽", 110, "e"),
            ("stock", "Наличие", 80, "center"),
        ):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col == "name"))
        self.tree.tag_configure("best", background="#d8f3dc")
        self.tree.tag_configure("out", foreground="#888888")
        # кнопки — под таблицей, чтобы не обрезались на узком окне
        bar = ttk.Frame(tab_search, padding=(0, 8, 0, 0))
        bar.pack(side="bottom", fill="x")
        self.fav_btn = ttk.Button(bar, text="★ В избранное", command=self._add_favorite, state="disabled")
        self.fav_btn.pack(side="left")
        self.open_btn = ttk.Button(bar, text="Открыть на сайте", command=self._open_selected, state="disabled")
        self.open_btn.pack(side="left", padx=8)
        ttk.Label(
            bar, text="Зелёным отмечен самый выгодный товар каждой сети. Двойной щелчок — открыть на сайте.",
            foreground="#555555",
        ).pack(side="left", padx=8)
        scroll = ttk.Scrollbar(tab_search, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())

        # --- вкладка «Избранное»
        tab_fav = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab_fav, text="Избранное")
        fcols = ("city", "chain", "name", "price", "saved")
        self.fav_tree = ttk.Treeview(tab_fav, columns=fcols, show="headings", selectmode="browse")
        for col, title, width, anchor in (
            ("city", "Город", 100, "w"),
            ("chain", "Магазин", 100, "w"),
            ("name", "Товар", 440, "w"),
            ("price", "Цена при сохранении, ₽", 190, "e"),
            ("saved", "Сохранено", 130, "center"),
        ):
            self.fav_tree.heading(col, text=title)
            self.fav_tree.column(col, width=width, anchor=anchor, stretch=(col == "name"))
        fbar = ttk.Frame(tab_fav, padding=(0, 8, 0, 0))
        fbar.pack(side="bottom", fill="x")
        self.fav_open_btn = ttk.Button(fbar, text="Открыть на сайте", command=self._open_favorite, state="disabled")
        self.fav_open_btn.pack(side="left")
        self.fav_del_btn = ttk.Button(fbar, text="Удалить", command=self._remove_favorite, state="disabled")
        self.fav_del_btn.pack(side="left", padx=8)
        fscroll = ttk.Scrollbar(tab_fav, orient="vertical", command=self.fav_tree.yview)
        self.fav_tree.configure(yscrollcommand=fscroll.set)
        fscroll.pack(side="right", fill="y")
        self.fav_tree.pack(side="left", fill="both", expand=True)
        self.fav_tree.bind("<Double-1>", lambda _e: self._open_favorite())
        self.fav_tree.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())

        self.status_var = tk.StringVar(value="Готово.")
        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 2)).pack(
            fill="x", side="bottom", pady=(6, 0)
        )

    # ------------------------------------------------------------ helpers
    def _parsers_for(self, demo: bool) -> dict[str, StoreChainParser]:
        if demo not in self._parsers:
            self._parsers[demo] = build_parsers(self.settings, demo)
        return self._parsers[demo]

    def _update_demo_banner(self) -> None:
        if self.demo_var.get():
            self.banner.config(text="ДЕМО-РЕЖИМ: цены вымышленные, интернет не используется.")
        else:
            self.banner.config(text="")

    def _on_demo_toggle(self) -> None:
        self.storage.set_setting("demo", "1" if self.demo_var.get() else "0")
        self._update_demo_banner()

    def _on_city_change(self, _event: object = None) -> None:
        self.storage.set_setting("city", self.city_var.get())
        self.status_var.set(f"Город: {self.city_var.get()}. Введите товар и нажмите «Найти».")

    def _update_buttons(self) -> None:
        state = "normal" if self.tree.selection() else "disabled"
        self.fav_btn.config(state=state)
        self.open_btn.config(state=state)
        fstate = "normal" if self.fav_tree.selection() else "disabled"
        self.fav_open_btn.config(state=fstate)
        self.fav_del_btn.config(state=fstate)

    # ------------------------------------------------------------- search
    def _start_search(self) -> None:
        if self._busy:
            return
        query = self.query_var.get().strip()
        if not query:
            messagebox.showinfo(APP_NAME, "Введите название товара.")
            return
        self._busy = True
        self.search_btn.config(state="disabled")
        self.status_var.set(f"Ищу «{query}» в г. {self.city_var.get()}…")
        city, demo = self.city_var.get(), self.demo_var.get()
        parsers = self._parsers_for(demo)
        limit = int(self.settings["results_per_store"])

        def worker() -> None:
            try:
                result = run_search(query, city, parsers, limit, self._store_cache if not demo else {}, demo)
                self._queue.put(("result", result))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("fatal", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                self._busy = False
                self.search_btn.config(state="normal")
                if kind == "result":
                    self._show_result(payload)
                else:
                    self.status_var.set("Ошибка поиска.")
                    messagebox.showerror(APP_NAME, payload)
        except queue.Empty:
            pass
        self.after(150, self._poll_queue)

    def _show_result(self, result: SearchResult) -> None:
        self.tree.delete(*self.tree.get_children())
        self._results.clear()
        best_ids = {(p.chain, p.product_id) for p in best_per_chain(result.products).values()}
        for product in sort_products(result.products):
            tags = []
            if (product.chain, product.product_id) in best_ids:
                tags.append("best")
            if not product.in_stock:
                tags.append("out")
            iid = self.tree.insert(
                "", "end",
                values=(
                    product.chain,
                    product.name,
                    f"{product.price:.2f}",
                    f"{product.old_price:.2f}" if product.old_price else "",
                    f"{product.unit_price:.2f} / {product.unit_label}" if product.unit_price is not None else "—",
                    "есть" if product.in_stock else "нет",
                ),
                tags=tags,
            )
            self._results[iid] = product
        text = verdict(result.products) if result.products else "Ничего не найдено."
        if result.errors:
            text += "\n" + "\n".join(f"⚠ {msg}" for msg in result.errors.values())
        self.verdict_var.set(text)
        stores = "; ".join(f"{c}: {s.address or s.code}" for c, s in result.stores.items())
        self.status_var.set(f"Найдено товаров: {len(result.products)}. Магазины — {stores}" if stores else "Готово.")
        self.notebook.select(0)
        self._update_buttons()

    # ---------------------------------------------------------- favorites
    def _selected_product(self) -> Product | None:
        sel = self.tree.selection()
        return self._results.get(sel[0]) if sel else None

    def _add_favorite(self) -> None:
        product = self._selected_product()
        if not product:
            return
        if product.is_demo:
            product = dataclasses.replace(product, name=f"{product.name} (демо)")
        is_new = self.storage.add_favorite(product, self.city_var.get())
        self._refresh_favorites()
        self.status_var.set(
            "Добавлено в избранное." if is_new else "Товар уже в избранном — цена и дата обновлены."
        )

    def _refresh_favorites(self) -> None:
        self.fav_tree.delete(*self.fav_tree.get_children())
        self._fav_ids.clear()
        self._fav_urls.clear()
        for fav in self.storage.list_favorites():
            iid = self.fav_tree.insert(
                "", "end",
                values=(fav.city, fav.chain, fav.name, f"{fav.price:.2f}", fav.saved_at),
            )
            self._fav_ids[iid] = fav.id
            self._fav_urls[iid] = fav.url
        self._update_buttons()

    def _remove_favorite(self) -> None:
        sel = self.fav_tree.selection()
        if not sel:
            return
        if messagebox.askyesno(APP_NAME, "Удалить товар из избранного?"):
            self.storage.remove_favorite(self._fav_ids[sel[0]])
            self._refresh_favorites()
            self.status_var.set("Удалено из избранного.")

    # ------------------------------------------------------------ links
    def _open_selected(self) -> None:
        product = self._selected_product()
        if product and product.url:
            webbrowser.open(product.url)

    def _open_favorite(self) -> None:
        sel = self.fav_tree.selection()
        if sel and self._fav_urls.get(sel[0]):
            webbrowser.open(self._fav_urls[sel[0]])

    def _on_close(self) -> None:
        self.storage.close()
        self.destroy()


def run(**kwargs: Any) -> None:
    App(**kwargs).mainloop()
