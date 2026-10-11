# BTC 生态项目代币监控模板

一个可直接运行、可按需扩展的 BTC 生态监控模板，覆盖 **RGB、Taproot Assets、Lightning、Runes、BRC-20 / Ordinals、BTC L2 / BTCFi** 等生态，从三个维度跟踪项目：

| 维度 | 数据源 | 说明 |
|---|---|---|
| 💰 代币价格表现 | CoinGecko | 价格、1h/24h/7d 涨跌、**相对 BTC 超额收益**、市值、成交量、量/市值、板块市值加权涨跌、涨跌榜 |
| 📢 最新项目公告 | GitHub Release、官方博客 RSS/Atom、X 官方账号 | 按生态 → 项目归类，按时间倒序 |
| 💬 用户反馈 | GitHub Issue、Reddit、X 搜索 | 中英文关键词情绪打分、热门讨论、负面反馈 / 风险线索 |

输出 Markdown 报告（`reports/YYYY-MM-DD.md`）+ JSON 快照（`data/`），并可把告警推送到 **Telegram / Discord / 飞书**。另附两份人工填写模板（日报/周报、项目档案）。

## 快速开始

```bash
cd btc-ecosystem-monitor
pip install -r requirements.txt

# 1) 离线演示：不联网，预览报告格式
python -m monitor --demo
cat reports/latest-demo.md

# 2) 实时采集（全部生态）
python -m monitor --no-notify

# 3) 只看 RGB + Taproot Assets，回看 72 小时
python -m monitor --ecosystem rgb --ecosystem taproot_assets --hours 72
```

## 目录结构

```
btc-ecosystem-monitor/
├── config/
│   ├── projects.yaml        # ★ 监控清单：生态、项目、代币、数据源
│   └── settings.yaml        # 回看窗口、告警阈值、通知渠道
├── monitor/
│   ├── __main__.py          # CLI 入口
│   ├── collectors/
│   │   ├── price.py         # CoinGecko 行情
│   │   ├── github.py        # Release（公告）+ Issue（反馈）
│   │   ├── rss.py           # 官方博客 RSS / Atom（公告）
│   │   └── social.py        # Reddit（反馈）+ X（公告/反馈）
│   ├── sentiment.py         # 中英文关键词情绪打分
│   ├── alerts.py            # 阈值告警 + Telegram/Discord/飞书推送
│   ├── report.py            # Markdown 报告渲染
│   └── demo.py              # 离线演示数据
├── templates/
│   ├── daily_report_template.md     # 人工日报 / 周报模板
│   └── project_profile_template.md  # 单项目档案模板
├── reports/                 # 生成的报告
├── data/                    # JSON 快照（可做历史回溯）
└── tests/
```

## 添加 / 修改监控项目

编辑 `config/projects.yaml`，每个项目的数据源都是可选的，缺哪个就跳过哪个维度：

```yaml
projects:
  - id: my-project              # 唯一 ID
    name: My Project
    ecosystem: rgb              # 必须是 ecosystems 中定义的 key
    token:
      symbol: ABC
      coingecko_id: abc-token   # CoinGecko 币种页 URL 中的 ID
    github: [org/repo]          # Release → 公告；Issue → 用户反馈
    rss: [https://blog.example.com/feed.xml]
    reddit_query: '"My Project" bitcoin'
    x_query: '"My Project" -is:retweet'
    x_handle: myproject         # 该账号的推文归为「公告」
    keywords: [ABC, My Project]
```

新增生态只需在 `ecosystems` 下加一个 key。配置中标注 **「待核实」** 的 CoinGecko ID / 链接请使用前确认；如果 ID 填错，报告附录会提示「CoinGecko 未返回数据」。

> 提示：Lightning、RGB、Taproot Assets 很多项目**没有自己的代币**（或资产是 USDT 等稳定币），模板对这类项目只跟踪公告与反馈；可在人工模板中补充网络容量、资产发行量等链上指标。

## 环境变量

| 变量 | 是否必需 | 用途 |
|---|---|---|
| `GITHUB_TOKEN` | 推荐 | GitHub API 限额从 60 提升到 5000 次/小时 |
| `COINGECKO_API_KEY` / `COINGECKO_PRO_API_KEY` | 推荐 | CoinGecko Demo / Pro Key，避免限流 |
| `X_BEARER_TOKEN` | 可选 | 开启 X(Twitter) 搜索采集 |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | 可选 | Telegram 告警 |
| `DISCORD_WEBHOOK_URL` | 可选 | Discord 告警 |
| `FEISHU_WEBHOOK_URL` | 可选 | 飞书群机器人告警 |

## 告警规则（`config/settings.yaml`）

| 规则 | 默认阈值 | 级别 |
|---|---|---|
| 24h 涨跌幅 | ±15%（±30% 升级为 critical） | warn / critical |
| 7d 涨跌幅 | ±35% | warn |
| 相对 BTC 24h 超额 | ±10 个百分点 | info |
| 成交量 / 市值 | ≥ 0.5 | warn |
| 负面反馈占比 | ≥ 40%（样本 ≥ 5） | warn |
| GitHub 新版本发布 | – | info |

只有 warn 及以上会推送到通知渠道，info 仅写入报告。

## 定时运行

- **GitHub Actions**：仓库已包含 `.github/workflows/btc-ecosystem-monitor.yml`，每天 08:17（UTC+8）运行并把报告提交到 `reports/`。在仓库 *Settings → Secrets and variables → Actions* 中配置上述环境变量即可；也可在 Actions 页面手动触发。
- **crontab**：`0 */4 * * * cd /path/to/btc-ecosystem-monitor && python -m monitor --hours 4`

## 扩展建议

- **情绪分析**：`sentiment.score()` 是关键词粗筛，可替换为 LLM 打分 / 摘要，以获得更准确的舆情结论。
- **更多数据源**：Telegram / Discord 群消息、Nostr、交易所公告、链上索引器（Ordiscan、UniSat、Taproot Assets Universe、mempool.space 闪电网络统计）等，按 `collectors/` 中的函数签名新增采集器并在 `__main__._collect_project` 中注册即可。
- **历史对比**：`data/` 中保存了每次运行的 JSON 快照，可用于周报的环比统计或绘制走势。

## 测试

```bash
python -m unittest discover -s tests -t .
```

---
仅供研究参考，不构成投资建议。
