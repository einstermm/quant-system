# Roadmap

## Phase 1: 工程骨架和安全边界

验收标准：

- 目录结构与系统边界清晰。
- `main.py` 不会启动实盘交易。
- 核心模型、订单意图、风控和执行路由有最小测试。
- Hummingbot API 适配层默认禁止 live submission。

状态：已完成第一版。

## Phase 2: 数据层

目标：

- 统一 K 线、成交、资金费率、订单簿快照的数据模型。
- 接入历史数据源，先支持本地文件或交易所公开接口。
- 建立数据质量检查：缺口、重复、乱序、异常价格、成交量异常。

验收标准：

- 可以下载或导入 BTC-USDT、ETH-USDT 的 1h K 线。
- 数据可被 `CandleRepository` 查询。
- 数据质量报告可输出到文件。

状态：已完成本地 CSV 导入第一版，后续再接公网数据源和持久化仓库。

Phase 2.1 状态：Binance spot public K 线下载器已实现，默认范围可配置为
`BTC-USDT`、`ETH-USDT`、`4h`、`2025-01-01` 到 `2026-01-01`。

Phase 2.2 状态：SQLite K 线仓库已实现，可把 CSV 数据导入本地 SQLite，并通过
同一 `CandleRepository` 接口查询。

Phase 2.3 状态：统一 `MarketDataService` 已实现，策略配置可以生成 `CandleQuery`，
并从 SQLite 检查回测数据覆盖是否完整。

## Phase 3: 回测研究

目标：

- 跑通 `crypto_momentum_v1` 的历史回测。
- 加入手续费、滑点、仓位约束和基础绩效指标。
- 保存参数、数据区间、结果和代码版本。

验收标准：

- 同一份配置可以复现实验结果。
- 输出 total return、max drawdown、turnover、fee、交易次数。
- 回测不会调用 Hummingbot。

状态：已完成第一版 `crypto_momentum_v1` 离线回测引擎，使用 SQLite 数据源和
JSON 结果输出。

Phase 3.1 状态：参数扫描和实验记录已实现，可批量扫描 fast/slow 窗口、手续费和滑点假设，
并输出 JSON/CSV 摘要。

Phase 3.2 状态：train/test 稳健性验证已实现，可按训练集排名并同时输出测试集表现。

Phase 3.3 状态：walk-forward 多折稳健性验证已实现，可在 2023-2026 数据上滚动训练和测试。

Phase 3.4 状态：市场状态过滤已实现，支持趋势强度和波动率阈值扫描。真实 walk-forward
结果未改善 baseline，策略仍不适合进入 paper trading。

Phase 3.5 状态：BTC/ETH 相对强弱轮动已实现，支持 lookback 和 min momentum 扫描。
walk-forward 中位数转正且正收益折数提升到 `6/10`，但尾部亏损扩大，仍不适合进入
paper trading。

Phase 3.6 状态：相对强弱 universe 已扩展到 BTC、ETH、BNB、SOL、XRP、ADA，并增加
`risk_adjusted` 参数选择模式，把训练集回撤、换手和 tail loss 纳入排名。最佳
walk-forward 结果为正收益折数 `7/10`、平均测试收益约 `10.86%`、中位约 `4.43%`，
但最差测试收益仍约 `-15.85%`，暂不进入 paper trading。

Phase 3.7 状态：组合级风险覆盖层已实现，支持波动率目标缩放、全局高水位熔断和单次
调仓换手上限。最佳 walk-forward 结果为正收益折数 `7/10`、平均测试收益约 `15.47%`、
中位约 `2.66%`，最差测试收益收敛到约 `-4.79%`，最差测试回撤约 `10.62%`。
该候选进入 paper trading 前还需要容量约束、执行约束和监控流程。

Phase 3.8 状态：执行容量约束已实现，支持最小下单额、K 线成交量参与率上限、容量估算
和 risk-off 恢复窗口。1 万 USDT 研究资金下容量约束未触发，选中测试折最小估算容量约
`23.12` 万 USDT；100 万 USDT 压力测试会触发参与率上限。

Phase 3.9 状态：paper readiness 检查、Markdown 日报和 risk-off 恢复手册已实现。
当前候选状态为 `paper_ready_with_warnings`，没有 CRITICAL 阻断，但需要人工确认收益
集中、risk-off 出现和大资金容量压力测试触发参与率上限。live trading 继续禁止。

## Phase 4: Paper Trading

目标：

- 实时行情进入 signal worker。
- 策略产生信号，组合生成目标，风控生成决策。
- trader gateway 只记录模拟订单，不触发真实交易。

验收标准：

- 可以连续运行 24 小时。
- 每个订单意图都有信号、组合、风控和执行日志。
- kill switch 可立即阻断新订单。

状态：Phase 4.2 已完成准实时 K 线刷新接入。当前能力包括：

- Phase 3.9 readiness JSON 启动前门禁。
- SQLite K 线读取、相对强弱目标权重生成、组合调仓差额计算。
- `max_rebalance_turnover`、`max_participation_rate`、`min_order_notional` 执行约束。
- 风险引擎审批、reduce-only 方向校验和本地 kill switch 阻断。
- `PaperExecutionClient` 即时模拟成交，JSONL ledger 重建 paper cash、position 和 equity。
- 定时 observation loop，支持 `--cycles`、`--duration-hours` 和 `--interval-seconds`。
- 每轮输出 observation JSONL，并生成 summary JSON 与 Markdown report。
- 每轮 cycle 前可用 `--refresh-market-data` 刷新 Binance spot 已收盘 K 线到 SQLite。
- observation log 会记录每个交易对的刷新状态、起止时间、拉取数量和错误信息。

Phase 4.2 验证：新增 market data refresh 单元测试，覆盖已收盘时间计算、增量拉取、
尾部 upsert 和 up-to-date 跳过；paper observation 单元测试覆盖 pre-cycle refresh payload。
公网 smoke 已成功刷新 Binance public K 线到 `2026-04-26T00:00:00+00:00` runtime end，
6 个交易对各新增/更新 `692` 根 4h K 线，本轮 paper observation 状态 `ok`，`2` 个
模拟订单全部通过风控。

剩余 Phase 4 工作：用真实 Binance public data 跑完整 24 小时 observation，复核 refresh、
数据完整性、订单、权益和拒单。live trading 继续禁止。

## Phase 5: Hummingbot Sandbox

目标：

- 把风险批准的订单意图映射为 Hummingbot Strategy V2 Controller/Executor 配置。
- 使用 sandbox 或极小资金账户验证订单生命周期。

验收标准：

- 订单创建、撤销、成交回报、对账链路完整。
- 交易所精度和最小下单量由 Hummingbot 处理。
- 系统能识别 Hummingbot 断连、订单异常和余额异常。

## Phase 6: Live Trading

目标：

- 小资金实盘。
- 增强监控、告警、日报和税务导出。

验收标准：

- `LIVE_TRADING_ENABLED=true` 需要显式配置。
- kill switch 默认可用。
- 每日自动生成账户、策略和风险报告。
