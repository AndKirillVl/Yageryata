import pytest
import requests

from zup.http import HttpClient, ParserError


class FakeResponse:
    def __init__(self, status=200, payload=None, bad_json=False):
        self.status_code = status
        self._payload = payload
        self._bad = bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._payload


def client(monkeypatch, response=None, exc=None):
    c = HttpClient("Сайт", {}, min_interval=0)

    def fake_request(*_a, **_k):
        if exc:
            raise exc
        return response

    monkeypatch.setattr(c.session, "request", fake_request)
    return c


def test_ok(monkeypatch):
    assert client(monkeypatch, FakeResponse(payload={"a": 1})).request_json("GET", "http://x") == {"a": 1}


@pytest.mark.parametrize("status, text", [(403, "защита от ботов"), (429, "слишком много"), (500, "HTTP 500")])
def test_http_errors_have_readable_messages(monkeypatch, status, text):
    with pytest.raises(ParserError, match=text):
        client(monkeypatch, FakeResponse(status=status)).request_json("GET", "http://x")


def test_not_json(monkeypatch):
    with pytest.raises(ParserError, match="JSON"):
        client(monkeypatch, FakeResponse(bad_json=True)).request_json("GET", "http://x")


@pytest.mark.parametrize(
    "exc, text",
    [
        (requests.exceptions.ConnectionError(), "нет соединения"),
        (requests.exceptions.Timeout(), "не ответил"),
        (requests.exceptions.ProxyError(), "прокси"),
        (requests.exceptions.TooManyRedirects(), "антибот"),
    ],
)
def test_network_errors(monkeypatch, exc, text):
    with pytest.raises(ParserError, match=text):
        client(monkeypatch, exc=exc).request_json("GET", "http://x")
