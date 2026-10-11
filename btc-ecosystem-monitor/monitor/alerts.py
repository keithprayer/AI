"""根据阈值生成告警，并推送到 Telegram / Discord / 飞书。"""
from __future__ import annotations

import os

from . import http
from .config import Config
from .models import ANNOUNCEMENT, FEEDBACK, Alert, Snapshot


def evaluate(cfg: Config, snap: Snapshot) -> list[Alert]:
    t = cfg.settings.get("alerts", {})
    alerts: list[Alert] = []

    for p in cfg.projects:
        q = snap.quotes.get(p.id)
        if q:
            tag = p.name if q.symbol in p.name else f"{p.name} ({q.symbol})"
            if q.change_24h is not None and abs(q.change_24h) >= t.get("price_change_24h_pct", 15):
                level = "critical" if abs(q.change_24h) >= 2 * t.get("price_change_24h_pct", 15) else "warn"
                alerts.append(Alert(level, p.id, f"{tag} 24h 涨跌 {q.change_24h:+.1f}%"))
            if q.change_7d is not None and abs(q.change_7d) >= t.get("price_change_7d_pct", 35):
                alerts.append(Alert("warn", p.id, f"{tag} 7d 涨跌 {q.change_7d:+.1f}%"))
            if q.excess_vs_btc_24h is not None and abs(q.excess_vs_btc_24h) >= t.get("excess_vs_btc_24h_pct", 10):
                word = "跑赢" if q.excess_vs_btc_24h > 0 else "跑输"
                alerts.append(Alert("info", p.id, f"{tag} 24h {word} BTC {abs(q.excess_vs_btc_24h):.1f} 个百分点"))
            ratio = q.volume_to_mcap
            if ratio is not None and ratio >= t.get("volume_to_mcap_ratio", 0.5):
                alerts.append(Alert("warn", p.id, f"{tag} 异常放量：成交量/市值 = {ratio:.2f}"))

        items = [i for i in snap.items if i.project_id == p.id]
        feedback = [i for i in items if i.kind == FEEDBACK]
        if len(feedback) >= t.get("min_feedback_samples", 5):
            neg_ratio = sum(1 for i in feedback if i.sentiment < -0.2) / len(feedback)
            if neg_ratio >= t.get("negative_feedback_ratio", 0.4):
                alerts.append(Alert("warn", p.id, f"{p.name} 负面反馈占比 {neg_ratio:.0%}（{len(feedback)} 条样本）"))
        if t.get("new_release", True):
            for i in items:
                if i.kind == ANNOUNCEMENT and i.source == "github-release":
                    alerts.append(Alert("info", p.id, f"{p.name} 新版本：{i.title}"))

    order = {"critical": 0, "warn": 1, "info": 2}
    return sorted(alerts, key=lambda a: order.get(a.level, 9))


def format_alerts(alerts: list[Alert], limit: int = 30) -> str:
    icon = {"critical": "🚨", "warn": "⚠️", "info": "ℹ️"}
    lines = [f"{icon.get(a.level, '•')} {a.message}" for a in alerts[:limit]]
    if len(alerts) > limit:
        lines.append(f"… 另有 {len(alerts) - limit} 条，详见报告")
    return "\n".join(lines)


def notify(cfg: Config, alerts: list[Alert], report_url: str | None = None) -> list[str]:
    """推送 warn 及以上级别告警。返回发送失败的错误信息列表。"""
    important = [a for a in alerts if a.level in ("critical", "warn")]
    if not important:
        return []
    text = "【BTC 生态监控告警】\n" + format_alerts(important)
    if report_url:
        text += f"\n报告：{report_url}"

    n = cfg.settings.get("notify", {})
    errors = []

    def env(section: str, key: str) -> str | None:
        name = n.get(section, {}).get(key)
        return os.getenv(name) if name else None

    targets = []
    if (token := env("telegram", "bot_token_env")) and (chat := env("telegram", "chat_id_env")):
        targets.append(("telegram", f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat, "text": text}))
    if url := env("discord", "webhook_env"):
        targets.append(("discord", url, {"content": text[:1990]}))
    if url := env("feishu", "webhook_env"):
        targets.append(("feishu", url, {"msg_type": "text", "content": {"text": text}}))

    for name, url, payload in targets:
        try:
            http.post_json(url, payload)
        except Exception as e:  # noqa: BLE001 - 通知失败不应中断主流程
            # 不直接输出异常文本：Telegram 的 URL 中含 bot token
            status = getattr(getattr(e, "response", None), "status_code", None)
            errors.append(f"notify/{name}: {type(e).__name__}" + (f" (HTTP {status})" if status else ""))
    return errors
