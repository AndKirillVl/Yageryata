"""Общий HTTP-слой: прокси, паузы между запросами, понятные ошибки."""

from __future__ import annotations

import threading
import time
from typing import Any

import requests


class ParserError(Exception):
    """Ошибка парсинга с сообщением, которое можно показать пользователю."""


class HttpClient:
    def __init__(
        self,
        site_name: str,
        headers: dict[str, str],
        *,
        proxy: str = "",
        timeout: float = 15,
        min_interval: float = 0.5,
    ) -> None:
        self.site_name = site_name
        self.timeout = timeout
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update(headers)
        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

    def _pace(self) -> None:
        with self._lock:
            wait = self._last_request + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Выполняет запрос и возвращает разобранный JSON либо бросает ParserError."""
        self._pace()
        try:
            resp = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.ProxyError as exc:
            raise ParserError(f"{self.site_name}: не удалось подключиться через прокси.") from exc
        except requests.exceptions.TooManyRedirects as exc:
            raise ParserError(
                f"{self.site_name}: сайт зациклил перенаправления — похоже на антибот-защиту. "
                "Укажите cookie из браузера в settings.json или используйте прокси."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise ParserError(f"{self.site_name}: сайт не ответил за {self.timeout:g} с.") from exc
        except requests.exceptions.RequestException as exc:
            raise ParserError(f"{self.site_name}: нет соединения с сайтом ({exc.__class__.__name__}).") from exc

        if resp.status_code in (401, 403):
            raise ParserError(
                f"{self.site_name}: доступ запрещён (HTTP {resp.status_code}) — сработала защита от ботов. "
                "Укажите cookie из браузера в settings.json или используйте прокси."
            )
        if resp.status_code == 429:
            raise ParserError(f"{self.site_name}: слишком много запросов (HTTP 429), повторите позже.")
        if resp.status_code >= 400:
            raise ParserError(f"{self.site_name}: ошибка сервера HTTP {resp.status_code}.")
        try:
            return resp.json()
        except ValueError as exc:
            raise ParserError(
                f"{self.site_name}: ответ не в формате JSON (возможно, показана страница проверки «я не робот»)."
            ) from exc
