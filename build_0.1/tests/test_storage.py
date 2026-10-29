from zup.models import Product
from zup.storage import Storage


def make(price=100.0, pid="1"):
    return Product("Магнит", pid, "Молоко 1л", price, unit_price=price, unit_label="л", url="https://magnit.ru/")


def test_settings_roundtrip():
    s = Storage(":memory:")
    assert s.get_setting("city", "Пенза") == "Пенза"
    s.set_setting("city", "Кузнецк")
    s.set_setting("city", "Заречный")
    assert s.get_setting("city") == "Заречный"


def test_favorites_add_list_remove():
    s = Storage(":memory:")
    assert s.add_favorite(make(), "Пенза") is True
    favs = s.list_favorites()
    assert len(favs) == 1 and favs[0].name == "Молоко 1л" and favs[0].city == "Пенза"
    s.remove_favorite(favs[0].id)
    assert s.list_favorites() == []


def test_duplicate_favorite_updates_price_not_count():
    s = Storage(":memory:")
    s.add_favorite(make(100.0), "Пенза")
    assert s.add_favorite(make(90.0), "Пенза") is False
    favs = s.list_favorites()
    assert len(favs) == 1 and favs[0].price == 90.0


def test_same_product_in_different_cities_are_separate():
    s = Storage(":memory:")
    s.add_favorite(make(), "Пенза")
    s.add_favorite(make(), "Кузнецк")
    assert len(s.list_favorites()) == 2


def test_persistence_between_connections(tmp_path):
    path = tmp_path / "zup.db"
    s = Storage(path)
    s.add_favorite(make(), "Пенза")
    s.close()
    assert len(Storage(path).list_favorites()) == 1
