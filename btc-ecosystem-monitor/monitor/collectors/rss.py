"""官方博客 / Medium / Substack 等 RSS 2.0 与 Atom 订阅源采集（项目公告）。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .. import http
from ..config import Project
from ..models import ANNOUNCEMENT, Item

ATOM = "{http://www.w3.org/2005/Atom}"


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        dt = parsedate_to_datetime(text)  # RFC 822（RSS）
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))  # ISO 8601（Atom）
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    for it in root.iter("item"):  # RSS 2.0
        entries.append(
            {
                "title": (it.findtext("title") or "").strip(),
                "url": (it.findtext("link") or "").strip(),
                "published": _parse_date(it.findtext("pubDate")),
                "body": _strip_html(it.findtext("description") or ""),
            }
        )
    for e in root.iter(f"{ATOM}entry"):  # Atom
        # 注意：无子节点的 Element 布尔值为 False，不能用 `or` 兜底
        link = e.find(f"{ATOM}link[@rel='alternate']")
        if link is None:
            link = e.find(f"{ATOM}link")
        entries.append(
            {
                "title": (e.findtext(f"{ATOM}title") or "").strip(),
                "url": link.get("href", "") if link is not None else "",
                "published": _parse_date(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated")),
                "body": _strip_html(e.findtext(f"{ATOM}summary") or e.findtext(f"{ATOM}content") or ""),
            }
        )
    return entries


def collect_rss(project: Project, since: datetime) -> list[Item]:
    items = []
    for feed_url in project.rss:
        for e in parse_feed(http.get(feed_url).text):
            if e["published"] is None or e["published"] < since:
                continue
            items.append(
                Item(
                    project_id=project.id,
                    kind=ANNOUNCEMENT,
                    source="rss",
                    title=e["title"],
                    url=e["url"],
                    published=e["published"],
                    body=e["body"][:500],
                )
            )
    return items
