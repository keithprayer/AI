"""GitHub Release（版本公告）与 Issue（用户反馈 / Bug 报告）采集。

建议设置 GITHUB_TOKEN，匿名额度只有 60 次/小时。
"""
from __future__ import annotations

import os
from datetime import datetime

from .. import http
from ..config import Project
from ..models import ANNOUNCEMENT, FEEDBACK, Item

API = "https://api.github.com"


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if token := os.getenv("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {token}"
    return h


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def collect_releases(project: Project, since: datetime, per_repo: int = 5) -> list[Item]:
    items = []
    for repo in project.github:
        for r in http.get_json(f"{API}/repos/{repo}/releases", params={"per_page": per_repo}, headers=_headers()):
            if r.get("draft") or not r.get("published_at"):
                continue
            published = _ts(r["published_at"])
            if published < since:
                continue
            tag = r.get("tag_name", "")
            title = f"[{repo}] {r.get('name') or tag}"
            if r.get("prerelease"):
                title += " (pre-release)"
            items.append(
                Item(
                    project_id=project.id,
                    kind=ANNOUNCEMENT,
                    source="github-release",
                    title=title,
                    url=r["html_url"],
                    published=published,
                    author=(r.get("author") or {}).get("login", ""),
                    body=(r.get("body") or "")[:500],
                )
            )
    return items


def collect_issues(project: Project, since: datetime, per_repo: int = 20) -> list[Item]:
    items = []
    for repo in project.github:
        rows = http.get_json(
            f"{API}/repos/{repo}/issues",
            params={"state": "all", "sort": "created", "direction": "desc", "since": since.isoformat(), "per_page": per_repo},
            headers=_headers(),
        )
        for r in rows:
            if "pull_request" in r:  # issues 接口也会返回 PR，过滤掉
                continue
            created = _ts(r["created_at"])
            if created < since:
                continue
            labels = ", ".join(l["name"] for l in r.get("labels", []))
            items.append(
                Item(
                    project_id=project.id,
                    kind=FEEDBACK,
                    source="github-issue",
                    title=f"[{repo}#{r['number']}] {r['title']}" + (f"  ({labels})" if labels else ""),
                    url=r["html_url"],
                    published=created,
                    author=(r.get("user") or {}).get("login", ""),
                    body=(r.get("body") or "")[:500],
                    engagement=r.get("comments", 0) + (r.get("reactions") or {}).get("total_count", 0),
                )
            )
    return items
