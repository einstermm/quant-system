# V0 Feature Inventory

生成日期：2026-04-28

当前版本定位：`v0 initial flow closed with warnings`。

这不是一套已经可以无人值守扩容运行的生产级量化系统；它是一套已经把“数据 -> 研究 -> paper -> Hummingbot paper -> 小资金 live -> 对账 -> 日报/税务导出 -> 冷却复盘 -> 初始闭环”跑通的初始版本。当前下一次 live decision 仍为 `NO_GO_COOLDOWN_ACTIVE`。

## 深度分级

| 等级 | 含义 |
| --- | --- |
| L0 | 只有设计或目录边界 |
| L1 | 本地代码实现并有单元测试 |
| L2 | 能用历史数据或样例数据跑通 |
| L3 | 能跑 paper trading / observation |
| L4 | 已接入 Hummingbot runtime 或真实 Hummingbot 导出 |
| L5 | 已完成受控小资金真实交易和事后对账 |

## 总体状态

| 领域 | 当前深度 | 状态 |
| --- | --- | --- |
| 工程骨架与安全边界 | L1 | 已建立模块边界，默认禁止 live submission |
| 市场数据层 | L2 | 已支持 Binance public K 线下载、CSV 导入、SQLite 查询、质量检查 |
| 策略研究 | L2 | 已完成多阶段回测、参数扫描、train/test、walk-forward 和 risk overlay |
| paper trading | L3 | 已完成本地 24 小时 paper observation |
| Hummingbot paper/sandbox | L4 | 已完成 Hummingbot CLI direct paper 2 小时 observation 和导出验收 |
| live readiness | L4 | 已完成 alert、凭据权限、allowlist、operator signoff、connector preflight |
| 小资金 live execution | L5 | 已完成 1 笔 BTC-USDT market buy，约 49.27 USDT |
| post-trade reconciliation | L5 | 已完成订单、成交、DB fill、余额和风险 cap 对账 |
| 报告与税务基础导出 | L5/L2 | live 报告已生成；税务导出仍是 validation-only，不可直接报税 |
| cooldown 与闭环治理 | L5 | 已生成 Phase 6.8 cooldown 和 Phase 6.9 initial closure |

## 已实现功能清单

### 1. 工程骨架与安全边界

- 已划分 `data`、`signals`、`portfolio`、`risk`、`execution`、`paper_trading`、`reporting`、`accounting`、`adapters/hummingbot` 等模块。
- `Hummingbot` 被定位为执行基础设施，不承载 alpha 和账户级风控。
- 默认安全姿态为 `LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`。
- Hummingbot API 适配层默认禁止 live submission。
- 真实交易所 API key 不放入 `quant-system/.env`，只允许放在 Hummingbot CLI connector 配置中。

深度：L1。

### 2. 市场数据层

- 支持 Binance spot public K 线下载。
- 支持 CSV K 线导入。
- 支持 SQLite K 线仓库。
- 支持统一 `CandleRepository` 查询接口。
- 支持数据质量检查：缺口、重复、乱序、异常价格和成交量异常。
- 支持按策略配置生成 `CandleQuery` 并检查回测数据覆盖。
- Phase 6.5 已能刷新 BTC/ETH public market data 并生成 live candidate package。

深度：L2。

### 3. 策略与研究

- 已实现 `crypto_momentum_v1` 基础动量策略。
- 已实现 `crypto_relative_strength_v1` 加密大币种相对强弱轮动策略。
- 支持 BTC、ETH、BNB、SOL、XRP、ADA universe 研究。
- 支持趋势强度、波动率、lookback、min momentum、risk-adjusted selection 等参数。
- 支持组合级 risk overlay：波动率目标缩放、全局高水位熔断、调仓换手上限。
- 支持容量约束：最小下单额、K 线成交量参与率上限、容量估算和 100 万 USDT 压力测试。

深度：L2。

### 4. 回测与稳健性验证

- 支持离线回测，包含手续费、滑点、仓位约束和基础绩效指标。
- 支持参数扫描并输出 JSON/CSV。
- 支持 train/test 验证。
- 支持 walk-forward 多折验证。
- 支持输出 total return、max drawdown、turnover、fee、trade count 等结果。
- Phase 3.7 最佳 walk-forward 结果显示最差测试收益收敛到约 `-4.79%`，但仍只作为 paper 前候选，不作为直接 live 依据。

深度：L2。

### 5. Paper Trading

- 支持从 SQLite K 线读取最新数据并生成策略目标。
- 支持组合目标到调仓订单意图。
- 支持风控审批、reduce-only 方向校验和本地 kill switch。
- 支持 `PaperExecutionClient` 即时模拟成交。
- 支持 JSONL ledger 重建 cash、position 和 equity。
- 支持 observation loop：`--cycles`、`--duration-hours`、`--interval-seconds`。
- 支持每轮 cycle 前 `--refresh-market-data` 刷新 Binance spot 已收盘 K 线。
- Phase 4.3 已跑满 24 小时 observation：`1397` 个 cycle、`failed_cycles=0`、`market_data_incomplete_cycles=0`、`rejected_orders=0`。

深度：L3。

### 6. Hummingbot Paper/Sandbox 集成

- 支持从 Phase 4 paper ledger 生成 Hummingbot sandbox manifest。
- 支持 controller config、orders JSONL、event schema、event capture template 和 operator runbook 输出。
- 支持 Hummingbot event JSONL 标准化：submitted、filled、completed、canceled、failed、disconnect、order exception、balance、heartbeat、session_completed。
- 支持 sandbox/paper reconciliation：订单数、成交数、终态、未知订单、缺失终态、成交数量和余额异常。
- 支持 runtime preflight，扫描 Hummingbot / Hummingbot API 挂载目录中的 connector credential config，只输出字段名，不输出密钥。
- 已识别并规避 Hummingbot API connector registry 不包含 `binance_paper_trade` 的限制，转向 Hummingbot CLI direct paper 路径。
- Phase 5.10 已完成 `7200` 秒 Hummingbot CLI direct paper observation，事件共 `397` 条，submitted `8`、filled `8`、terminal `8`，failed/canceled/unknown/missing 均为 `0`。

深度：L4。

### 7. Live Readiness 与人工准入

- Phase 6.1 支持 live readiness preflight 和 Hummingbot daily report。
- Phase 6.2 支持 live activation checklist。
- 已生成严格 live risk 配置：
  - `max_order_notional=250`
  - `max_symbol_notional=500`
  - `max_gross_notional=1000`
  - `max_daily_loss=50`
  - `max_drawdown_pct=0.05`
- 已记录外部告警通道验证。
- 已记录交易所凭据权限范围和 allowlist：
  - connector：`binance`
  - account：主账户
  - market：spot
  - withdrawal / transfer / futures / leverage 权限关闭
  - read / spot trading 权限开启
  - IP 白名单开启
  - 首次交易对：`BTC-USDT`、`ETH-USDT`
- 已记录 operator activation signoff。
- Phase 6.3 已完成 Hummingbot live connector preflight，只输出字段名，不输出 API key 或 secret。

深度：L4。

### 8. 首次小资金 Live Batch

- Phase 6.4 已生成首次小资金 live batch activation plan。
- Phase 6.5 已刷新 BTC/ETH public market data 并生成候选订单包。
- 低资金版批次范围：
  - 最多 `1` 笔订单
  - 批次总名义金额不超过 `50 USDT`
  - 单笔不超过 `50 USDT`
  - 交易对仅 `BTC-USDT`、`ETH-USDT`
- Phase 6.6 已生成一次性 Hummingbot live runner 并安装到本机 Hummingbot 挂载目录。
- 已执行真实小资金 live order：
  - pair：`BTC-USDT`
  - side：market buy
  - gross notional：`49.266880 USDT`
  - gross base：`0.00064 BTC`
  - net base：`0.00063936 BTC`
  - average fill price：`76979.5 USDT`
- 已执行过的 one-shot runner config 已 disarm：`live_order_submission_armed=false`。

深度：L5。

### 9. 成交后对账、日报和税务基础导出

- Phase 6.7 已完成 post-trade reconciliation。
- 对账结果：
  - submitted/filled/db fills：`1/1/1`
  - 无 missing submissions
  - 无 missing fills
  - 无 DB fill mismatch
  - 余额 delta 通过：`USDT -49.26688000`、`BTC +0.00063936`
  - 风险 cap、order count、allowlist 和 price deviation 均通过
- 已生成：
  - post-trade report
  - daily report
  - normalized live trades JSONL
  - trade/tax export CSV
  - trade/tax export summary
- 当前 tax export 仍使用 `validation_only_not_tax_filing`，正式报税前必须接入真实 CAD FX source 和加拿大 ACB lot matching。

深度：L5，税务最终可用性为 L2。

### 10. Cooldown、初始闭环与仓位生命周期

- Phase 6.8 已生成 live cooldown review。
- 冷却窗口：
  - start/completed timestamp：`2026-04-28T02:34:33.175500+00:00`
  - minimum cooldown：`24` 小时
  - next review not before：`2026-04-29T02:34:33.175500+00:00`
- 已确认：
  - event log 最后一条为 `session_completed`
  - one-shot runner container 不存在
  - 原 `hummingbot` 容器停止
  - runner config 已 disarm
  - 人工检查 Binance open orders 为 `confirmed_clean`
- Phase 6.9 已生成 initial closure and position lifecycle report。
- 当前 BTC 仓位计划：`HOLD_UNDER_OBSERVATION`。
- 不自动退出；如需退出，必须另行生成并审批 one-shot sell plan。

深度：L5。

### 11. 报告、证据和可审计性

- 已生成 backtest reports、paper readiness reports、paper trading reports、Hummingbot sandbox reports、live readiness reports。
- 每个阶段有 JSON/Markdown 输出，适合后续归档。
- live 阶段形成了从 activation 到 post-trade 到 cooldown 的证据链。
- 当前仓库报告中会记录交易时间、数量、价格、余额 delta 和本地文件路径；提交远程仓库前应确认这些信息是否可以被你接受。

深度：L4/L5。

### 12. 测试覆盖

- 当前 unit test 文件数：`36`。
- 最近完整单元测试结果：`./venv/bin/python -m unittest discover -s tests/unit` 通过，`115` 个测试 OK。
- 覆盖范围包括：
  - market data
  - SQLite candle repository
  - backtest engine
  - train/test validation
  - walk-forward
  - risk engine
  - paper trading
  - Hummingbot sandbox reconciliation
  - Hummingbot observation review
  - live activation
  - live connector preflight
  - live one-batch runner
  - live post-trade
  - live cooldown
  - live initial closure
  - tax export

深度：L1 到 L5 关键路径均有测试或真实运行证据。

## 当前明确不是生产级的部分

- 不是无人值守的全天候 live trading 系统。
- 没有批准下一次 live batch；当前仍被 cooldown gate 阻断。
- 没有自动扩大交易对、订单数量或资金上限。
- 没有生产级实时风险守护进程。
- 没有多账户、多交易所资金统一调度。
- 没有高可用部署、故障转移和恢复演练。
- MQTT bridge warning 尚未解决或正式关闭。
- 税务导出不能直接用于正式报税。
- BTC 小仓位只有 hold-under-observation 计划，没有自动退出策略。
- 当前 alpha 仍是初始研究候选，不应视为稳定收益策略。

## Git 提交前建议

1. 保留 `v0` 语义：这是“完整流程跑通版”，不是“生产自动交易版”。
2. 提交前检查是否要把 `reports/` 中的真实成交细节放入远程仓库。
3. 不提交 Hummingbot 外部目录中的 connector secrets。
4. 保持 live runner disarmed。
5. 在冷却窗口结束后重跑 Phase 6.8，补一份 cooldown completed 报告。
6. Phase 7 优先建设 production control plane：实时风险守护、被动监控、runbook freeze、正式审计 manifest、position lifecycle exit plan、正式 tax/ACB pipeline。

## 一句话结论

当前 v0 已经达到“受控小资金实盘闭环验证”的深度；还没有达到“可规模化、无人值守、机构生产级运行”的深度。下一阶段不应继续重造交易 bot 基础能力，而应把重点放在 Hummingbot 上层的风控治理、审计、监控、仓位生命周期和研究到实盘的一致性控制。
