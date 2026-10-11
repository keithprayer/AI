import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from monitor import alerts, report, sentiment
from monitor.__main__ import main
from monitor.collectors.rss import parse_feed
from monitor.config import load_config
from monitor.demo import build_demo
from monitor.models import FEEDBACK, Item, PriceQuote, Snapshot, utcnow

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Taproot Assets v0.7</title><link>https://example.com/a</link>
<pubDate>Sat, 11 Oct 2026 08:00:00 GMT</pubDate><description>&lt;p&gt;Hello&lt;/p&gt;</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>RGB mainnet</title><link href="https://example.com/b"/>
<updated>2026-10-11T08:00:00Z</updated><summary>Released</summary></entry></feed>"""


class ConfigTest(unittest.TestCase):
    def test_default_config_loads(self):
        cfg = load_config()
        self.assertTrue(cfg.projects)
        for eco in ("rgb", "taproot_assets", "lightning"):
            self.assertIn(eco, cfg.ecosystems)
            self.assertTrue(cfg.by_ecosystem()[eco])


class SentimentTest(unittest.TestCase):
    def test_scores(self):
        self.assertGreater(sentiment.score("Mainnet launched, great upgrade"), 0.2)
        self.assertLess(sentiment.score("Funds stuck, wallet crash, looks like a scam"), -0.2)
        self.assertLess(sentiment.score("转账卡住，无法提现"), -0.2)
        self.assertEqual(sentiment.score("hello world"), 0.0)


class FeedTest(unittest.TestCase):
    def test_rss_and_atom(self):
        rss = parse_feed(RSS)
        self.assertEqual(rss[0]["url"], "https://example.com/a")
        self.assertEqual(rss[0]["body"], "Hello")
        self.assertIsNotNone(rss[0]["published"])
        atom = parse_feed(ATOM)
        self.assertEqual(atom[0]["url"], "https://example.com/b")
        self.assertEqual(atom[0]["published"].year, 2026)


class AlertTest(unittest.TestCase):
    def test_thresholds(self):
        cfg = load_config()
        p = next(p for p in cfg.projects if p.coingecko_id)
        snap = Snapshot(generated_at=utcnow())
        snap.quotes[p.id] = PriceQuote(p.id, p.symbol, 1.0, 100.0, 80.0, 0, 40.0, 5.0, 38.0)
        now = utcnow()
        snap.items = [
            Item(p.id, FEEDBACK, "reddit", "t", "u", now - timedelta(hours=1), sentiment=-0.8) for _ in range(5)
        ]
        msgs = [(a.level, a.message) for a in alerts.evaluate(cfg, snap)]
        self.assertEqual(msgs[0][0], "critical")  # 40% >= 2 * 15%
        joined = " ".join(m for _, m in msgs)
        self.assertIn("异常放量", joined)
        self.assertIn("负面反馈占比", joined)
        self.assertIn("跑赢 BTC", joined)


class ReportTest(unittest.TestCase):
    def test_demo_report_renders(self):
        cfg = load_config()
        snap = Snapshot(generated_at=utcnow())
        snap.quotes, snap.items = build_demo(cfg)
        md = report.render(cfg, snap, 24)
        for heading in ("## 2. 告警", "## 3. 代币价格表现", "## 4. 最新项目公告", "## 5. 用户反馈与舆情"):
            self.assertIn(heading, md)

    def test_cli_demo(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(["--demo", "--out", d, "--data", d, "--ecosystem", "rgb"]), 0)
            self.assertTrue((Path(d) / "latest-demo.md").exists())


if __name__ == "__main__":
    unittest.main()
