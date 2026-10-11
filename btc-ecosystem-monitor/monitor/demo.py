"""离线演示数据：不联网即可预览报告格式（python -m monitor --demo）。"""
from __future__ import annotations

import random
from datetime import timedelta

from .config import Config
from .models import ANNOUNCEMENT, FEEDBACK, Item, PriceQuote, utcnow

_FEEDBACK = [
    "Transfer stuck for hours, cannot finalize channel",
    "Wallet sync works smooth after the upgrade, great job",
    "Is the mainnet launch delayed again?",
    "转账一直卡住，客服无法联系",
    "新版本体验很顺畅，支持资产闪电转账了",
    "How do I back up my assets before migration?",
    "Looks like a rug, team silent for weeks",
    "Integration with exchange is live, adoption growing",
]


def build_demo(cfg: Config, seed: int = 42) -> tuple[dict[str, PriceQuote], list[Item]]:
    rnd = random.Random(seed)
    now = utcnow()
    btc_24h = rnd.uniform(-3, 3)
    quotes = {
        "__benchmark__": PriceQuote("__benchmark__", "BTC", 112_000 + rnd.uniform(-3000, 3000), 2.2e12, 4.5e10,
                                    rnd.uniform(-1, 1), btc_24h, rnd.uniform(-8, 8))
    }
    items: list[Item] = []
    for p in cfg.projects:
        if p.coingecko_id:
            mcap = rnd.uniform(5e7, 3e9)
            ch24 = rnd.uniform(-25, 25)
            quotes[p.id] = PriceQuote(
                p.id, p.symbol or "?", rnd.uniform(0.001, 5), mcap, mcap * rnd.uniform(0.02, 0.8),
                rnd.uniform(-3, 3), ch24, rnd.uniform(-45, 45), ch24 - btc_24h,
            )
        if p.github and rnd.random() < 0.5:
            repo = p.github[0]
            items.append(Item(p.id, ANNOUNCEMENT, "github-release", f"[{repo}] v0.{rnd.randint(1, 20)}.0",
                              f"https://github.com/{repo}/releases", now - timedelta(hours=rnd.uniform(0, 24))))
        if p.rss:
            items.append(Item(p.id, ANNOUNCEMENT, "rss", f"{p.name} 月度进展更新", p.rss[0],
                              now - timedelta(hours=rnd.uniform(0, 24))))
        for _ in range(rnd.randint(0, 7)):
            text = rnd.choice(_FEEDBACK)
            src = rnd.choice(["reddit", "github-issue", "x"])
            items.append(Item(p.id, FEEDBACK, src, text, "https://example.com/demo",
                              now - timedelta(hours=rnd.uniform(0, 24)), engagement=rnd.randint(0, 300), body=text))
    return quotes, items
