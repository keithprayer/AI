"""CoinGecko 价格 / 市值 / 成交量采集。

免费 Demo Key 可在 https://www.coingecko.com/en/api 申请，设置环境变量 COINGECKO_API_KEY；
Pro Key 设置 COINGECKO_PRO_API_KEY。未设置时使用公共匿名额度（容易限流）。
"""
from __future__ import annotations

import os

from .. import http
from ..config import Config
from ..models import PriceQuote


def _endpoint() -> tuple[str, dict]:
    if key := os.getenv("COINGECKO_PRO_API_KEY"):
        return "https://pro-api.coingecko.com/api/v3", {"x-cg-pro-api-key": key}
    headers = {}
    if key := os.getenv("COINGECKO_API_KEY"):
        headers["x-cg-demo-api-key"] = key
    return "https://api.coingecko.com/api/v3", headers


def collect_prices(cfg: Config) -> dict[str, PriceQuote]:
    """返回 {project_id: PriceQuote}，基准资产使用 key "__benchmark__"。"""
    id_to_projects: dict[str, list] = {}
    for p in cfg.projects:
        if p.coingecko_id:
            id_to_projects.setdefault(p.coingecko_id, []).append(p)
    ids = sorted(set(id_to_projects) | {cfg.benchmark_id})

    base, headers = _endpoint()
    rows = http.get_json(
        f"{base}/coins/markets",
        params={
            "vs_currency": cfg.settings.get("vs_currency", "usd"),
            "ids": ",".join(ids),
            "price_change_percentage": "1h,24h,7d",
            "per_page": 250,
        },
        headers=headers,
    )

    quotes: dict[str, PriceQuote] = {}
    benchmark_24h = None
    for row in rows:
        def quote(project_id: str, symbol: str) -> PriceQuote:
            return PriceQuote(
                project_id=project_id,
                symbol=symbol,
                price=row.get("current_price"),
                market_cap=row.get("market_cap"),
                volume_24h=row.get("total_volume"),
                change_1h=row.get("price_change_percentage_1h_in_currency"),
                change_24h=row.get("price_change_percentage_24h_in_currency"),
                change_7d=row.get("price_change_percentage_7d_in_currency"),
            )

        if row["id"] == cfg.benchmark_id:
            quotes["__benchmark__"] = quote("__benchmark__", row.get("symbol", "").upper())
            benchmark_24h = quotes["__benchmark__"].change_24h
        for p in id_to_projects.get(row["id"], []):
            quotes[p.id] = quote(p.id, p.symbol or row.get("symbol", "").upper())

    if benchmark_24h is not None:
        for q in quotes.values():
            if q.change_24h is not None:
                q.excess_vs_btc_24h = q.change_24h - benchmark_24h
    return quotes


def missing_ids(cfg: Config, quotes: dict[str, PriceQuote]) -> list[str]:
    """配置了 coingecko_id 但没有拿到行情的项目（通常是 ID 填错）。"""
    return [p.id for p in cfg.projects if p.coingecko_id and p.id not in quotes]
