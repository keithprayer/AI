from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Project:
    id: str
    name: str
    ecosystem: str
    symbol: str | None = None
    coingecko_id: str | None = None
    github: list[str] = field(default_factory=list)
    rss: list[str] = field(default_factory=list)
    reddit_query: str | None = None
    x_query: str | None = None
    x_handle: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class Config:
    ecosystems: dict[str, dict]
    projects: list[Project]
    benchmark_id: str
    settings: dict

    def project(self, project_id: str) -> Project:
        return next(p for p in self.projects if p.id == project_id)

    def by_ecosystem(self) -> dict[str, list[Project]]:
        groups: dict[str, list[Project]] = {k: [] for k in self.ecosystems}
        for p in self.projects:
            groups.setdefault(p.ecosystem, []).append(p)
        return groups


def load_config(projects_path: Path | None = None, settings_path: Path | None = None) -> Config:
    projects_path = projects_path or ROOT / "config" / "projects.yaml"
    settings_path = settings_path or ROOT / "config" / "settings.yaml"
    raw = yaml.safe_load(projects_path.read_text(encoding="utf-8"))
    settings = yaml.safe_load(settings_path.read_text(encoding="utf-8"))

    ecosystems = raw.get("ecosystems", {})
    projects = []
    seen = set()
    for p in raw.get("projects", []):
        if p["id"] in seen:
            raise ValueError(f"重复的项目 id: {p['id']}")
        if p["ecosystem"] not in ecosystems:
            raise ValueError(f"项目 {p['id']} 的 ecosystem '{p['ecosystem']}' 未在 ecosystems 中定义")
        seen.add(p["id"])
        token = p.get("token") or {}
        projects.append(
            Project(
                id=p["id"],
                name=p["name"],
                ecosystem=p["ecosystem"],
                symbol=token.get("symbol"),
                coingecko_id=token.get("coingecko_id"),
                github=p.get("github", []),
                rss=p.get("rss", []),
                reddit_query=p.get("reddit_query"),
                x_query=p.get("x_query"),
                x_handle=p.get("x_handle"),
                keywords=p.get("keywords", []),
            )
        )
    benchmark_id = (raw.get("benchmark") or {}).get("coingecko_id", "bitcoin")
    return Config(ecosystems=ecosystems, projects=projects, benchmark_id=benchmark_id, settings=settings)
