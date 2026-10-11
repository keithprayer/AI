from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

ANNOUNCEMENT = "announcement"
FEEDBACK = "feedback"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PriceQuote:
    project_id: str
    symbol: str
    price: float | None
    market_cap: float | None = None
    volume_24h: float | None = None
    change_1h: float | None = None
    change_24h: float | None = None
    change_7d: float | None = None
    excess_vs_btc_24h: float | None = None

    @property
    def volume_to_mcap(self) -> float | None:
        if self.volume_24h and self.market_cap:
            return self.volume_24h / self.market_cap
        return None


@dataclass
class Item:
    """一条公告或用户反馈。"""

    project_id: str
    kind: str  # ANNOUNCEMENT | FEEDBACK
    source: str  # github-release / github-issue / rss / reddit / x
    title: str
    url: str
    published: datetime
    author: str = ""
    body: str = ""
    engagement: int = 0  # 点赞 / 评论数等互动量
    sentiment: float = 0.0  # [-1, 1]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d


@dataclass
class Alert:
    level: str  # info / warn / critical
    project_id: str
    message: str


@dataclass
class Snapshot:
    generated_at: datetime
    quotes: dict[str, PriceQuote] = field(default_factory=dict)
    items: list[Item] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "quotes": {k: asdict(v) for k, v in self.quotes.items()},
            "items": [i.to_dict() for i in self.items],
            "alerts": [asdict(a) for a in self.alerts],
            "errors": self.errors,
        }
