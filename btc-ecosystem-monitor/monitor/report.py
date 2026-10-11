"""把一次采集结果渲染为 Markdown 监控报告。"""
from __future__ import annotations

from datetime import timedelta, timezone

from .alerts import format_alerts
from .config import Config
from .models import ANNOUNCEMENT, FEEDBACK, Item, PriceQuote, Snapshot
from .sentiment import label

CST = timezone(timedelta(hours=8))
SOURCE_NAME = {
    "github-release": "GitHub Release",
    "github-issue": "GitHub Issue",
    "rss": "官方博客",
    "reddit": "Reddit",
    "x": "X",
}


def _pct(v: float | None) -> str:
    if v is None:
        return "–"
    arrow = "🟢" if v > 0 else "🔴" if v < 0 else "⚪"
    return f"{arrow} {v:+.2f}%"


def _money(v: float | None) -> str:
    if v is None:
        return "–"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= div:
            return f"${v / div:.2f}{unit}"
    return f"${v:,.2f}"


def _price(v: float | None) -> str:
    if v is None:
        return "–"
    return f"${v:,.2f}" if v >= 1 else f"${v:.6g}"


def _when(item: Item) -> str:
    return item.published.astimezone(CST).strftime("%m-%d %H:%M")


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _weighted_change(quotes: list[PriceQuote]) -> float | None:
    rows = [(q.market_cap, q.change_24h) for q in quotes if q.market_cap and q.change_24h is not None]
    total = sum(m for m, _ in rows)
    return sum(m * c for m, c in rows) / total if total else None


def render(cfg: Config, snap: Snapshot, lookback_hours: int) -> str:
    groups = cfg.by_ecosystem()
    out: list[str] = []
    w = out.append
    now = snap.generated_at.astimezone(CST)

    w(f"# BTC 生态项目监控报告 · {now:%Y-%m-%d}")
    w("")
    w(f"> 生成时间：{now:%Y-%m-%d %H:%M} (UTC+8) ｜ 回看窗口：{lookback_hours}h ｜ "
      f"监控项目：{len(cfg.projects)} 个 ｜ 公告 {sum(i.kind == ANNOUNCEMENT for i in snap.items)} 条 ｜ "
      f"反馈 {sum(i.kind == FEEDBACK for i in snap.items)} 条 ｜ 告警 {len(snap.alerts)} 条")
    w("")

    # ---------------- 1. 核心结论 ----------------
    w("## 1. 今日核心结论（人工填写）")
    w("")
    w("- **市场：** <!-- 例：BTC 横盘，RGB 板块受 USDT 上线消息带动跑赢大盘 -->")
    w("- **公告：** <!-- 最重要的 1~3 条项目进展 -->")
    w("- **舆情：** <!-- 用户反馈中的集中问题或正面信号 -->")
    w("- **行动项：** <!-- 需要跟进 / 调研 / 调整仓位的事项 -->")
    w("")

    # ---------------- 2. 告警 ----------------
    w("## 2. 告警")
    w("")
    w(format_alerts(snap.alerts, limit=50).replace("\n", "\n\n") if snap.alerts else "暂无触发阈值的告警。")
    w("")

    # ---------------- 3. 价格表现 ----------------
    w("## 3. 代币价格表现")
    w("")
    if b := snap.quotes.get("__benchmark__"):
        w(f"**基准 BTC：** {_price(b.price)} ｜ 1h {_pct(b.change_1h)} ｜ 24h {_pct(b.change_24h)} ｜ 7d {_pct(b.change_7d)}")
        w("")

    priced = [snap.quotes[p.id] for p in cfg.projects if p.id in snap.quotes]
    if priced:
        ranked = sorted((q for q in priced if q.change_24h is not None), key=lambda q: q.change_24h, reverse=True)
        if ranked:
            w("**24h 涨幅榜：** " + "、".join(f"{q.symbol} {q.change_24h:+.1f}%" for q in ranked[:3]))
            w("")
            w("**24h 跌幅榜：** " + "、".join(f"{q.symbol} {q.change_24h:+.1f}%" for q in ranked[::-1][:3]))
            w("")

    for eco_id, projects in groups.items():
        quotes = [snap.quotes[p.id] for p in projects if p.id in snap.quotes]
        if not quotes:
            continue
        eco = cfg.ecosystems.get(eco_id, {})
        wc = _weighted_change(quotes)
        w(f"### {eco.get('name', eco_id)}" + (f"（市值加权 24h：{wc:+.2f}%）" if wc is not None else ""))
        w("")
        w("| 项目 | 代币 | 价格 | 1h | 24h | 7d | 24h vs BTC | 市值 | 24h 成交量 | 量/市值 |")
        w("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for p in projects:
            q = snap.quotes.get(p.id)
            if not q:
                continue
            ratio = q.volume_to_mcap
            w(f"| {p.name} | {q.symbol} | {_price(q.price)} | {_pct(q.change_1h)} | {_pct(q.change_24h)} | "
              f"{_pct(q.change_7d)} | {_pct(q.excess_vs_btc_24h)} | {_money(q.market_cap)} | "
              f"{_money(q.volume_24h)} | {f'{ratio:.2f}' if ratio is not None else '–'} |")
        w("")

    no_token = [p.name for p in cfg.projects if not p.coingecko_id]
    if no_token:
        w(f"<sub>无可交易代币 / 未配置行情的项目：{'、'.join(no_token)}</sub>")
        w("")

    # ---------------- 4. 项目公告 ----------------
    w("## 4. 最新项目公告")
    w("")
    any_ann = False
    for eco_id, projects in groups.items():
        block = []
        for p in projects:
            anns = sorted((i for i in snap.items if i.project_id == p.id and i.kind == ANNOUNCEMENT),
                          key=lambda i: i.published, reverse=True)
            for i in anns:
                block.append(f"- `{_when(i)}` **{p.name}** · {SOURCE_NAME.get(i.source, i.source)}：[{_esc(i.title)}]({i.url})")
        if block:
            any_ann = True
            w(f"### {cfg.ecosystems.get(eco_id, {}).get('name', eco_id)}")
            w("")
            out.extend(block)
            w("")
    if not any_ann:
        w("回看窗口内暂无新公告。")
        w("")

    # ---------------- 5. 用户反馈 ----------------
    w("## 5. 用户反馈与舆情")
    w("")
    rows = []
    for p in cfg.projects:
        fb = [i for i in snap.items if i.project_id == p.id and i.kind == FEEDBACK]
        if not fb:
            continue
        pos = sum(i.sentiment > 0.2 for i in fb)
        neg = sum(i.sentiment < -0.2 for i in fb)
        avg = sum(i.sentiment for i in fb) / len(fb)
        rows.append((p, fb, pos, len(fb) - pos - neg, neg, avg))
    if rows:
        w("| 项目 | 生态 | 样本 | 正面 | 中性 | 负面 | 平均情绪 |")
        w("|---|---|---:|---:|---:|---:|---|")
        for p, fb, pos, mid, neg, avg in sorted(rows, key=lambda r: len(r[1]), reverse=True):
            w(f"| {p.name} | {cfg.ecosystems.get(p.ecosystem, {}).get('name', p.ecosystem)} | {len(fb)} | "
              f"{pos} | {mid} | {neg} | {avg:+.2f}（{label(avg)}） |")
        w("")

        all_fb = [i for r in rows for i in r[1]]
        hot = sorted(all_fb, key=lambda i: i.engagement, reverse=True)[:10]
        w("### 热门讨论（按互动量）")
        w("")
        for i in hot:
            w(f"- `{_when(i)}` **{cfg.project(i.project_id).name}** · {SOURCE_NAME.get(i.source, i.source)} · "
              f"互动 {i.engagement} · {label(i.sentiment)}：[{_esc(i.title)}]({i.url})")
        w("")

        negative = sorted((i for i in all_fb if i.sentiment < -0.2), key=lambda i: i.sentiment)[:10]
        if negative:
            w("### 负面反馈 / 风险线索")
            w("")
            for i in negative:
                w(f"- `{_when(i)}` **{cfg.project(i.project_id).name}** · {SOURCE_NAME.get(i.source, i.source)} · "
                  f"情绪 {i.sentiment:+.2f}：[{_esc(i.title)}]({i.url})")
            w("")
    else:
        w("回看窗口内暂无采集到的用户反馈。")
        w("")

    # ---------------- 6. 人工研判 ----------------
    w("## 6. 人工研判与跟进（人工填写）")
    w("")
    w("| 生态 | 叙事 / 催化剂变化 | 风险事件 | 待跟进 | 负责人 |")
    w("|---|---|---|---|---|")
    for eco_id in groups:
        w(f"| {cfg.ecosystems.get(eco_id, {}).get('name', eco_id)} |  |  |  |  |")
    w("")

    # ---------------- 附录 ----------------
    if snap.errors:
        w("## 附录：采集异常")
        w("")
        for e in snap.errors:
            w(f"- {e}")
        w("")

    w("---")
    w("<sub>数据来源：CoinGecko、GitHub、项目 RSS、Reddit、X。情绪分为关键词粗筛结果，仅供参考，不构成投资建议。</sub>")
    return "\n".join(out) + "\n"
