"""轻量级中英文关键词情绪打分（无需模型 / API）。

仅用于粗筛：分数 > 0.2 视为正面，< -0.2 视为负面。需要更准确时可替换 score() 为 LLM 调用。
"""
from __future__ import annotations

import re

POSITIVE = {
    # en
    "launch", "launched", "release", "released", "mainnet", "partnership", "integrat", "listing", "listed",
    "bullish", "great", "awesome", "love", "works", "fast", "smooth", "adoption", "milestone", "upgrade",
    "support", "growth", "record", "secure", "success",
    # zh
    "上线", "发布", "主网", "合作", "集成", "上架", "看涨", "利好", "好用", "顺畅", "突破", "里程碑", "升级", "支持", "增长", "新高",
}
NEGATIVE = {
    # en
    "bug", "crash", "fail", "failed", "error", "stuck", "lost", "scam", "rug", "hack", "exploit", "vulnerab",
    "delay", "broken", "bearish", "dump", "slow", "problem", "refund", "fraud", "panic", "unlock",
    "can't", "cannot", "doesn't work", "not working",
    # zh
    "失败", "卡住", "丢失", "骗局", "跑路", "被盗", "漏洞", "攻击", "延期", "崩溃", "看跌", "利空", "砸盘", "解锁", "无法", "报错", "退款", "维权",
}

_word = re.compile(r"[a-z']+")


def _count(text: str, lexicon: set[str]) -> int:
    n = 0
    for term in lexicon:
        if term.isascii():
            # 英文按词前缀匹配（integrat -> integrate/integration），短语直接子串匹配
            if " " in term:
                n += text.count(term)
            else:
                n += sum(1 for w in _word.findall(text) if w.startswith(term))
        else:
            n += text.count(term)
    return n


def score(text: str) -> float:
    text = (text or "").lower()
    pos, neg = _count(text, POSITIVE), _count(text, NEGATIVE)
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 2)


def label(value: float) -> str:
    if value > 0.2:
        return "正面"
    if value < -0.2:
        return "负面"
    return "中性"
