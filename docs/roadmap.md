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

## Phase 4: Paper Trading

目标：

- 实时行情进入 signal worker。
- 策略产生信号，组合生成目标，风控生成决策。
- trader gateway 只记录模拟订单，不触发真实交易。

验收标准：

- 可以连续运行 24 小时。
- 每个订单意图都有信号、组合、风控和执行日志。
- kill switch 可立即阻断新订单。

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
