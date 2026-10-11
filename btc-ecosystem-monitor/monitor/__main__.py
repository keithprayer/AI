"""命令行入口。

    python -m monitor                 # 实时采集，生成报告并推送告警
    python -m monitor --demo          # 使用离线演示数据预览报告
    python -m monitor --hours 72 --ecosystem rgb --ecosystem taproot_assets --no-notify
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from . import alerts, report, sentiment
from .collectors import github, price, rss, social
from .config import ROOT, Config, Project, load_config
from .models import Item, Snapshot, utcnow


def _collect_project(cfg: Config, p: Project, since) -> tuple[list[Item], list[str]]:
    c = cfg.settings.get("collectors", {})
    tasks = []
    if p.github:
        tasks.append(("github-release", lambda: github.collect_releases(p, since, c.get("github", {}).get("releases_per_repo", 5))))
        tasks.append(("github-issue", lambda: github.collect_issues(p, since, c.get("github", {}).get("issues_per_repo", 20))))
    if p.rss:
        tasks.append(("rss", lambda: rss.collect_rss(p, since)))
    if p.reddit_query:
        tasks.append(("reddit", lambda: social.collect_reddit(p, since, c.get("reddit", {}).get("limit", 25))))
    if p.x_query and social.x_enabled():
        tasks.append(("x", lambda: social.collect_x(p, since, c.get("x", {}).get("max_results", 25))))

    items, errors = [], []
    for name, fn in tasks:
        try:
            items.extend(fn())
        except Exception as e:  # noqa: BLE001 - 单个数据源失败不影响整体
            errors.append(f"{p.id}/{name}: {type(e).__name__}: {e}")
    return items, errors


def collect(cfg: Config, hours: int, workers: int = 6) -> Snapshot:
    snap = Snapshot(generated_at=utcnow())
    since = snap.generated_at - timedelta(hours=hours)

    try:
        snap.quotes = price.collect_prices(cfg)
        for pid in price.missing_ids(cfg, snap.quotes):
            snap.errors.append(f"{pid}/price: CoinGecko 未返回数据，请核实 coingecko_id")
    except Exception as e:  # noqa: BLE001
        snap.errors.append(f"price: {type(e).__name__}: {e}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for items, errors in pool.map(lambda p: _collect_project(cfg, p, since), cfg.projects):
            snap.items.extend(items)
            snap.errors.extend(errors)
    return snap


def _dedupe(items: list[Item]) -> list[Item]:
    seen, out = set(), []
    for i in items:
        key = (i.project_id, i.url, i.title)
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m monitor", description="BTC 生态项目代币监控")
    ap.add_argument("--demo", action="store_true", help="使用离线演示数据")
    ap.add_argument("--hours", type=int, help="公告 / 反馈回看小时数（默认读取 settings.yaml）")
    ap.add_argument("--ecosystem", action="append", help="只监控指定生态，可重复，如 --ecosystem rgb")
    ap.add_argument("--projects", type=Path, help="自定义 projects.yaml 路径")
    ap.add_argument("--settings", type=Path, help="自定义 settings.yaml 路径")
    ap.add_argument("--out", type=Path, default=ROOT / "reports", help="报告输出目录")
    ap.add_argument("--data", type=Path, default=ROOT / "data", help="JSON 快照输出目录")
    ap.add_argument("--no-notify", action="store_true", help="不推送告警")
    ap.add_argument("--report-url", help="告警消息中附带的报告链接")
    args = ap.parse_args(argv)

    cfg = load_config(args.projects, args.settings)
    if args.ecosystem:
        unknown = set(args.ecosystem) - set(cfg.ecosystems)
        if unknown:
            ap.error(f"未知生态：{', '.join(sorted(unknown))}；可选：{', '.join(cfg.ecosystems)}")
        cfg.projects = [p for p in cfg.projects if p.ecosystem in args.ecosystem]
        cfg.ecosystems = {k: v for k, v in cfg.ecosystems.items() if k in args.ecosystem}
    hours = args.hours or cfg.settings.get("lookback_hours", 24)

    if args.demo:
        from .demo import build_demo

        snap = Snapshot(generated_at=utcnow())
        snap.quotes, snap.items = build_demo(cfg)
    else:
        snap = collect(cfg, hours)

    snap.items = _dedupe(snap.items)
    for i in snap.items:
        i.sentiment = sentiment.score(f"{i.title} {i.body}")
    snap.alerts = alerts.evaluate(cfg, snap)

    args.out.mkdir(parents=True, exist_ok=True)
    args.data.mkdir(parents=True, exist_ok=True)
    stamp = snap.generated_at.astimezone(report.CST)
    suffix = "-demo" if args.demo else ""
    md = report.render(cfg, snap, hours)
    report_path = args.out / f"{stamp:%Y-%m-%d}{suffix}.md"
    report_path.write_text(md, encoding="utf-8")
    (args.out / f"latest{suffix}.md").write_text(md, encoding="utf-8")
    (args.data / f"snapshot-{stamp:%Y%m%dT%H%M}{suffix}.json").write_text(
        json.dumps(snap.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not args.no_notify and not args.demo:
        for err in alerts.notify(cfg, snap.alerts, args.report_url):
            print(f"[warn] {err}", file=sys.stderr)

    print(f"报告：{report_path}")
    print(f"项目 {len(cfg.projects)} ｜ 行情 {len(snap.quotes)} ｜ 条目 {len(snap.items)} ｜ "
          f"告警 {len(snap.alerts)} ｜ 采集异常 {len(snap.errors)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
