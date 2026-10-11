from __future__ import annotations

import time

import requests

USER_AGENT = "btc-ecosystem-monitor/0.1 (+https://github.com/keithprayer/AI)"
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def get(url: str, *, params=None, headers=None, timeout: int = 20, retries: int = 2) -> requests.Response:
    """带简单重试（429 / 5xx）的 GET。"""
    for attempt in range(retries + 1):
        resp = _session.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(2 ** (attempt + 1))
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError("unreachable")


def get_json(url: str, **kwargs):
    return get(url, **kwargs).json()


def post_json(url: str, payload: dict, timeout: int = 20) -> None:
    _session.post(url, json=payload, timeout=timeout).raise_for_status()
