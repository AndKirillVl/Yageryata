import json

import pytest

from zup.config import CITIES, DEFAULT_SETTINGS, load_settings


def test_defaults_when_file_missing(tmp_path):
    assert load_settings(tmp_path / "none.json") == DEFAULT_SETTINGS


def test_override_and_unknown_keys_ignored(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"proxy": "http://h:1", "evil": 1}), encoding="utf-8")
    s = load_settings(p)
    assert s["proxy"] == "http://h:1" and "evil" not in s and s["timeout_sec"] == 15


def test_broken_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{oops", encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(p)


def test_penza_region_cities():
    assert "Пенза" in CITIES and len(CITIES) >= 10
    assert all(52 < c.lat < 54.5 and 42 < c.lon < 47.5 for c in CITIES.values())
