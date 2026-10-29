"""Дымовой тест окна: запускается только если есть tkinter и графический дисплей."""

import time

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app(tmp_path):
    from zup.gui import App

    try:
        window = App(demo=True, city="Пенза", db_path=str(tmp_path / "t.db"))
    except tk.TclError:
        pytest.skip("нет графического дисплея")
    yield window
    window.destroy()


def pump(app, seconds=3.0, until=lambda: False):
    end = time.time() + seconds
    while time.time() < end and not until():
        app.update()
        time.sleep(0.02)


def test_demo_search_favorite_flow(app):
    app.query_var.set("молоко")
    app._start_search()
    pump(app, until=lambda: len(app.tree.get_children()) > 0)
    rows = app.tree.get_children()
    assert len(rows) >= 4
    assert "Выгоднее" in app.verdict_var.get() or "Цены одинаковы" in app.verdict_var.get()
    assert "ДЕМО" in app.banner.cget("text")

    app.tree.selection_set(rows[0])
    app.update()
    assert str(app.fav_btn.cget("state")) == "normal"
    app._add_favorite()
    assert len(app.fav_tree.get_children()) == 1
    assert "(демо)" in app.fav_tree.item(app.fav_tree.get_children()[0], "values")[2]


def test_city_persisted(app):
    app.city_var.set("Кузнецк")
    app._on_city_change()
    assert app.storage.get_setting("city") == "Кузнецк"


def test_empty_result_message(app):
    app.query_var.set("несуществующийтовар")
    app._start_search()
    pump(app, until=lambda: "Ничего не найдено" in app.verdict_var.get())
    assert "Ничего не найдено" in app.verdict_var.get()
