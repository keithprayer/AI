"""社区与社交媒体：Reddit（用户反馈）与 X / Twitter（公告 + 反馈）。

- Reddit 使用公开 search.json，无需认证，但请控制频率。
- X 使用 API v2 recent search，需要环境变量 X_BEARER_TOKEN；未设置则跳过。
  来自 x_handle 官方账号的推文归为「公告」，其余归为「用户反馈」。
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from .. import http
from ..config import Project
from ..models import ANNOUNCEMENT, FEEDBACK, Item


def collect_reddit(project: Project, since: datetime, limit: int = 25) -> list[Item]:
    if not project.reddit_query:
        return []
    data = http.get_json(
        "https://www.reddit.com/search.json",
        params={"q": project.reddit_query, "sort": "new", "t": "week", "limit": limit},
    )
    items = []
    for child in data.get("data", {}).get("children", []):
        d = child["data"]
        published = datetime.fromtimestamp(d["created_utc"], tz=timezone.utc)
        if published < since:
            continue
        items.append(
            Item(
                project_id=project.id,
                kind=FEEDBACK,
                source="reddit",
                title=f"[r/{d.get('subreddit')}] {d.get('title', '')}",
                url="https://www.reddit.com" + d.get("permalink", ""),
                published=published,
                author=d.get("author", ""),
                body=(d.get("selftext") or "")[:500],
                engagement=d.get("score", 0) + d.get("num_comments", 0),
            )
        )
    return items


def x_enabled() -> bool:
    return bool(os.getenv("X_BEARER_TOKEN"))


def collect_x(project: Project, since: datetime, max_results: int = 25) -> list[Item]:
    if not project.x_query or not x_enabled():
        return []
    data = http.get_json(
        "https://api.twitter.com/2/tweets/search/recent",
        params={
            "query": project.x_query,
            "max_results": max(10, min(max_results, 100)),
            "start_time": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "username",
        },
        headers={"Authorization": f"Bearer {os.environ['X_BEARER_TOKEN']}"},
    )
    users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
    official = (project.x_handle or "").lower()
    items = []
    for t in data.get("data", []):
        username = users.get(t.get("author_id"), "")
        m = t.get("public_metrics", {})
        items.append(
            Item(
                project_id=project.id,
                kind=ANNOUNCEMENT if official and username.lower() == official else FEEDBACK,
                source="x",
                title=t["text"].replace("\n", " ")[:140],
                url=f"https://x.com/{username or 'i'}/status/{t['id']}",
                published=datetime.fromisoformat(t["created_at"].replace("Z", "+00:00")),
                author=username,
                body=t["text"],
                engagement=m.get("like_count", 0) + m.get("retweet_count", 0) + m.get("reply_count", 0),
            )
        )
    return items
