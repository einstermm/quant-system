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

状态：Phase 4.3 已完成 24 小时 paper observation 复盘与 Phase 5 决策门槛。当前能力包括：

- Phase 3.9 readiness JSON 启动前门禁。
- SQLite K 线读取、相对强弱目标权重生成、组合调仓差额计算。
- `max_rebalance_turnover`、`max_participation_rate`、`min_order_notional` 执行约束。
- 风险引擎审批、reduce-only 方向校验和本地 kill switch 阻断。
- `PaperExecutionClient` 即时模拟成交，JSONL ledger 重建 paper cash、position 和 equity。
- 定时 observation loop，支持 `--cycles`、`--duration-hours` 和 `--interval-seconds`。
- 每轮输出 observation JSONL，并生成 summary JSON 与 Markdown report。
- 每轮 cycle 前可用 `--refresh-market-data` 刷新 Binance spot 已收盘 K 线到 SQLite。
- observation log 会记录每个交易对的刷新状态、起止时间、拉取数量和错误信息。
- 24 小时复盘报告会输出运行稳定性、权益、订单、刷新质量、readiness WARN 和 Phase 5 决策。

Phase 4.2 验证：新增 market data refresh 单元测试，覆盖已收盘时间计算、增量拉取、
尾部 upsert 和 up-to-date 跳过；paper observation 单元测试覆盖 pre-cycle refresh payload。
公网 smoke 已成功刷新 Binance public K 线到 `2026-04-26T00:00:00+00:00` runtime end，
6 个交易对各新增/更新 `692` 根 4h K 线，本轮 paper observation 状态 `ok`，`2` 个
模拟订单全部通过风控。

Phase 4.3 结果：24 小时 observation 跑满 `1397` 个 cycle，`failed_cycles=0`、
`market_data_incomplete_cycles=0`、`rejected_orders=0`，净收益约 `+0.3534%`，
最大回撤约 `0.1887%`。决策为 `sandbox_ready_with_warnings`，WARN 来自 Phase 3.9
readiness。下一步允许准备 Phase 5 Hummingbot Sandbox；live trading 继续禁止。

## Phase 5: Hummingbot Sandbox

目标：

- 把风险批准的订单意图映射为 Hummingbot Strategy V2 Controller/Executor 配置。
- 使用 sandbox 或极小资金账户验证订单生命周期。

验收标准：

- 订单创建、撤销、成交回报、对账链路完整。
- 交易所精度和最小下单量由 Hummingbot 处理。
- 系统能识别 Hummingbot 断连、订单异常和余额异常。

状态：Phase 5.9 已完成 Hummingbot CLI direct paper observation-window smoke。
当前能力包括：

- 从 Phase 4.3 observation review 和 paper ledger 生成 Hummingbot sandbox manifest。
- 按交易对聚合 controller config，并把每笔 paper order 映射为 sandbox order config。
- manifest 强制 `live_trading_enabled=false`，精度和最小下单量检查交给 Hummingbot。
- 本地模拟 submitted/filled 生命周期，检查 client id 重复、提交数、终态数、断连、
  订单异常和余额异常。
- 输出 JSON manifest、JSON report 和 Markdown runbook。
- 读取 Hummingbot sandbox/paper event JSONL，标准化 submitted、filled、completed、
  canceled、failed、disconnect、order exception 和 balance 事件。
- 对 manifest 期望订单和实际事件做订单、成交、异常和余额对账。
- 汇总 Phase 5 manifest、Phase 5 准备报告、Phase 5.1 对账报告和当前安全环境，
  生成 sandbox session gate。
- gate 会阻断 live trading、交易所 key 环境变量、上游 blocked、缺失真实 event JSONL、
  订单/余额对账失败等情况。
- 生成外部 Hummingbot sandbox/paper dry run handoff package，包括 manifest、
  controller configs、orders JSONL、event schema、event capture template 和 operator runbook。
- 接收一个 Hummingbot event JSONL，自动重跑 reconciliation、session gate 和 handoff package，
  并输出 acceptance report。
- 扫描本机 Hummingbot / Hummingbot API 挂载目录中的 connector credential config，只输出
  connector 名称和敏感字段名，不输出密钥值。
- 在启动真实 Hummingbot sandbox 前阻断 live connector、真实交易所密钥字段和缺失 paper/testnet
  connector 的环境。
- 从 sandbox manifest 和 Phase 5.5 runtime preflight 生成 Hummingbot CLI paper-mode handoff，
  包含自定义 Strategy V2 controller、controller YAML、`v2_with_controllers.py` script YAML
  和操作手册。
- 已把 Phase 5.6 文件安装到本机 Hummingbot CLI 挂载目录，并用 Hummingbot conda 环境完成
  controller 语法和 YAML 解析校验。
- Phase 5.7 增加 direct paper script handoff，绕开当前 Hummingbot paper connector 与
  Strategy V2 `OrderExecutor` 的 `_order_tracker` 兼容性问题，直接用 `binance_paper_trade`
  提交 paper buy/sell。
- direct paper 事件会写出 `submitted_amount`、`requested_amount` 和 paper 余额裁剪原因；
  reconciliation 会按 Hummingbot 实际提交量核对成交数量，并把裁剪作为 WARN 留痕。
- Phase 5.8 会复盘真实 Hummingbot acceptance 和 event JSONL，输出进入更长 observation
  window 前的准入结论、carry-forward WARN 和 operator runbook。
- Phase 5.9 direct paper handoff 支持最短运行时间、heartbeat、周期余额快照、final balance
  snapshot 和 `session_completed` 事件，避免订单批次成交后立即结束而无法观察 runtime 窗口。

Phase 5 准备结果：`sandbox_prepared_with_warnings`。本次生成 `3` 个 controller config、
`8` 个 sandbox order config，总名义金额约 `2003.6605 USDT`；本地生命周期检查显示
submitted `8`、terminal `8`、duplicate client ids `0`、disconnect/order exception/
balance anomaly 均为 `0`。WARN 仍来自 Phase 3.9/Phase 4.3 readiness。

Phase 5.1 replay 结果：`sandbox_reconciled`。本次生成并对账 `20` 条事件，其中 submitted
`8`、filled `8`、balance `4`；未知订单、缺失终态、成交数量不一致和余额不一致均为 `0`。

Phase 5.2 replay gate 结果：`sandbox_session_ready_with_warnings`。当前环境
`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`、未检测到交易所 key 环境变量；
WARN 来自 Phase 5 准备报告 warning 和 replay 事件源。

Phase 5.3 package 结果：`sandbox_package_ready_with_warnings`。当前包包含 `3` 个
controller config、`8` 笔 sandbox order、event schema/template 和 operator runbook；
WARN 来自 replay gate，因此只能用于第一次外部 dry run。

Phase 5.4 replay acceptance 结果：`sandbox_export_accepted_with_warnings`。reconciliation
为 `sandbox_reconciled`，session gate 和 package 仍因 replay source 带 WARN。

Phase 5.5 本机 runtime preflight 初始结果为 `blocked`：`hummingbot-api` 挂载目录中存在
`master_account/binance_perpetual` live connector 配置，并包含 API key/secret 字段。该 connector
已被移出 `credentials/master_account/connectors` 自动扫描目录并归档保留；隔离后预检结果为
`runtime_ready`，未发现可加载 connector credential config，且 `conf_client.yml` 中识别到
`binance_paper_trade` paper 设置。`hummingbot-api`、broker 和 postgres 已安全启动，本地
`GET /` 返回 running，最近启动日志没有真实 Binance account 初始化错误。

已确认的限制：当前 `hummingbot-api` 的 connector registry 不包含 `binance_paper_trade`，
调用 `binance_paper_trade/config-map` 会失败。因此第一次真实 Hummingbot paper dry run 应优先
走 Hummingbot CLI paper mode；不要通过 API trading connector 路由提交订单。live trading 继续禁止。

Phase 5.6 结果：`cli_paper_handoff_ready`。生成目录为
`reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_6_cli_paper_handoff`；已安装到
`/Users/albertlz/Downloads/private_proj/hummingbot` 的文件包括：

- `controllers/generic/quant_system_sandbox_order_controller.py`
- `conf/controllers/crypto_relative_strength_v1_phase_5_6_ada_usdt.yml`
- `conf/controllers/crypto_relative_strength_v1_phase_5_6_btc_usdt.yml`
- `conf/controllers/crypto_relative_strength_v1_phase_5_6_xrp_usdt.yml`
- `conf/scripts/crypto_relative_strength_v1_phase_5_6_v2_with_controllers.yml`

Phase 5.6 runtime 发现：controller handoff 可编译和加载，但 Hummingbot paper connector 与
Strategy V2 `OrderExecutor` 路径会触发 `_order_tracker` 兼容性错误，因此不作为当前验收路径。

Phase 5.7 direct paper 结果：`cli_direct_paper_handoff_ready`，真实 Hummingbot paper export
验收结果为 `sandbox_export_accepted_with_warnings`。本轮使用
`/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_7_hummingbot_events.jsonl`
采集 `26` 条事件：submitted `8`、filled `8`、balance `10`；failed/canceled/unknown/missing
均为 `0`。WARN 来自 1 笔 XRP 卖单因 paper 可用余额裁剪 `0.6038357768 XRP`、实时 fill 价格
相对 manifest 价格偏移、手续费偏移，以及 Hummingbot paper 初始余额与 Phase 4 账户余额不同导致
余额数量核对跳过。live trading 继续禁止。

Phase 5.8 observation-window gate 结果：`hummingbot_observation_window_ready_with_warnings`。
报告为 `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_8_observation_review.md`。
本轮真实 export 覆盖约 `0.0111` 小时，低于目标 `2` 小时，因此只能视为进入更长窗口前的
短批次验收。订单层面仍为 submitted `8`、filled `8`、terminal `8`、failed/canceled/unknown
均为 `0`。下一步可以准备更长 Hummingbot CLI direct paper observation window，但必须先从
最新批准的 paper ledger 重新生成 manifest，不要盲目重复提交旧订单。live trading 继续禁止。

Phase 5.9 observation-window smoke 结果：重新从 Phase 4.3 review 和 24h paper ledger 生成
`reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_9_sandbox_manifest.json`，并生成
`crypto_relative_strength_v1_phase_5_9_direct_paper_observation.yml`。本轮 Hummingbot CLI paper
运行最短 `120` 秒，事件文件为
`/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_9_hummingbot_events.jsonl`。
验收结果为 `sandbox_export_accepted_with_warnings`，observation review 为
`hummingbot_observation_window_ready_with_warnings`。事件共 `85` 条：submitted `8`、filled `8`、
heartbeat `9`、balance `58`、session_started `1`、session_completed `1`；failed/canceled/
unknown/missing 均为 `0`。下一步可启动目标 `2h` 的 direct paper observation window；live trading
继续禁止。

Phase 5.10 2h observation 结果：重新生成 Phase 5.10 manifest 和 r2 handoff 后，完成
`7200` 秒 Hummingbot CLI direct paper observation。事件文件为
`/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_10_r2_hummingbot_events.jsonl`。
验收结果为 `sandbox_export_accepted_with_warnings`，observation review 为
`hummingbot_observation_window_ready_with_warnings`。事件共 `397` 条：submitted `8`、filled `8`、
terminal `8`、heartbeat `121`、balance `258`、session_completed `1`；failed/canceled/
unknown/missing 均为 `0`。WARN 继续来自 paper 可用余额裁剪、fill price drift、fee drift 和
balance reconciliation skipped。

## Phase 6: Live Trading

目标：

- 小资金实盘。
- 增强监控、告警、日报和税务导出。

验收标准：

- `LIVE_TRADING_ENABLED=true` 需要显式配置。
- kill switch 默认可用。
- 每日自动生成账户、策略和风险报告。

Phase 6.1 live readiness preflight 结果：新增 Hummingbot daily report 和只读 live readiness
gate。该步骤不提交真实订单、不读取或输出密钥值。当前结果为
`live_preflight_ready_with_warnings`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_1_live_readiness.md`；日报位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.md`。

当前 warnings：

- Phase 5.10 acceptance / observation warning 需要带入 live runbook。
- Phase 6.2 已验证 Telegram 外部告警通道。
- `strategies/crypto_relative_strength_v1/risk.yml` 的 `max_order_notional=1000` 高于 Phase 6.1
  初始小资金单笔上限 `250`，首次 live activation 前应生成更严格的 live risk 配置。

Phase 6.2 live activation checklist 结果：新增严格 live risk 配置
`strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml`，单笔上限降为 `250`、单币种
上限 `500`、总 gross 上限 `1000`、日亏损上限 `50`、最大回撤 `5%`。同时从 Phase 5.10
Hummingbot filled events 生成 trade/tax export CSV 和 summary。当前 tax export 状态为
`tax_export_ready_with_warnings`，共 `8` 行，WARN 来自 validation-only CAD FX source 和
加拿大 ACB lot matching 仍需后处理。

Phase 6.2 activation checklist 当前结果为 `live_activation_ready`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.md`。
自动通过项包括 Phase 6.1 readiness、daily report、trade tax export、严格 live risk cap、
`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true` 和 Telegram alert test。凭据权限范围、
交易所 allowlist 和操作员 signoff 已由操作员确认并记录到 Phase 6.2 artifacts。
live trading 继续禁止，Phase 6.3 才允许准备真实 live connector handoff。

Phase 6.3 live connector preflight 结果：新增 Hummingbot live connector 配置交接和预检入口。
该步骤读取 Phase 6.2 activation checklist、credential allowlist、operator signoff 和严格 live
risk 配置，扫描本机 Hummingbot connector 配置目录，但只输出字段名，不输出 API key 或 secret
值。当前结果为 `live_connector_preflight_ready`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.md`。

已通过项包括 Phase 6.2 activation、凭据权限/allowlist、操作员 signoff、严格 live risk、
`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`、Telegram alert channel，以及交易所 key
未放入 `quant-system` 环境变量。Hummingbot CLI connector 文件
`/Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors/binance.yml` 已存在，且必需字段名
`binance_api_key`、`binance_api_secret` 已检测到。下一步进入首次小资金 live batch activation
plan；live trading 继续禁止，直到单独 activation。

Phase 6.4 first live batch activation plan 结果：新增首次小资金 live batch 执行计划入口。
该步骤只生成计划和门禁，不打开 live 开关、不提交订单。当前结果为
`live_batch_activation_plan_approved`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan_low_funds_50.md`。

当前有效低资金版批次范围固定为单批次、最多 `1` 笔订单、总名义金额上限 `50 USDT`、单笔上限 `50 USDT`、
交易对仅 `BTC-USDT` 和 `ETH-USDT`。已通过 Phase 6.3 connector preflight、allowlist、严格
live risk、`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`、外部告警和密钥隔离检查。
operator final go 已确认，但 `live_order_submission_armed=false`。live trading 继续禁止，直到
生成并手动启动 one-batch live runner。

Phase 6.5 candidate live batch package 结果：刷新 BTC/ETH public market data 后，基于最新已
收盘 4h K 线生成候选订单包。当前结果为
`live_batch_execution_package_ready_pending_exchange_state_check`，输出目录为
`reports/live_readiness/crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50`。

本轮 BTC/ETH-only 信号只选中 `BTC-USDT`，候选订单为 market buy，估算名义 `50 USDT`，
估算价格 `77371.32000000`，估算数量 `0.0006462342893981904405921987631`。该阶段未生成 live
runner，`live_order_submission_armed=false`。操作员已确认低资金版 exchange state check：
Binance spot 可用 USDT 足够覆盖 `50 USDT` 买入和手续费、没有异常 open orders，且当前
BTC/ETH/USDT 持仓不会让本批次超过风险上限。

Phase 6.6 live one-batch runner 结果：基于低资金版候选订单生成并安装一次性 Hummingbot live
runner。当前结果为 `live_one_batch_runner_ready`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.md`。

已安装到 Hummingbot 挂载目录：
`/Users/albertlz/Downloads/private_proj/hummingbot/scripts/quant_system_live_one_batch.py` 和
`/Users/albertlz/Downloads/private_proj/hummingbot/conf/scripts/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`。
事件日志目标为
`/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`。
该 runner 已在人工确认后启动并完成首次低资金 live batch；完成后一次性 runner 容器已停止。

Phase 6.7 live post-trade reconciliation 结果：首次真实成交已完成对账、日报和 trade/tax export。
当前结果为 `live_post_trade_reconciled_with_warnings`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.md`。

成交结果：`BTC-USDT` market buy，submitted/filled/db fills 为 `1/1/1`，gross notional
`49.266880 USDT`，gross base `0.00064 BTC`，手续费 `0.00000064 BTC`，net base
`0.00063936 BTC`，平均成交价 `76979.5 USDT`。余额对账通过：`USDT -49.26688000`，
`BTC +0.00063936`，无 missing submissions/fills，无余额 mismatch，名义金额、order count、
allowlist 和 price deviation 均在低资金 cap 内。

输出文件包括 daily report、post-trade reconciliation、normalized live trades JSONL 和
trade/tax export CSV。WARN 仅来自 MQTT bridge 未连接以及 validation-only tax FX source；
不得据此自动扩大交易对、订单数或风险额度。

Phase 6.8 live cooldown review 结果：首次 live batch 已进入 24 小时冷却复盘。当前结果为
`live_cooldown_active_with_warnings`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/cooldown_review.md`。

冷却窗口从 `2026-04-28T02:34:33.175500+00:00` 开始，下一次 review 不早于
`2026-04-29T02:34:33.175500+00:00`。本次检查确认 event log 最后一条事件为
`session_completed`，一次性 runner 容器不存在，原 `hummingbot` 容器仍停止，已执行过的
Hummingbot runner config 已 disarm（`live_order_submission_armed=false`）。Phase 6.8
明确禁止新增 live batch、扩大交易对或提高 `50 USDT` 低资金 cap。操作员已完成 Binance
open orders 人工检查，结果为 `confirmed_clean`，未发现异常 open orders；冷却期内只允许继续复盘，
以及处理 MQTT bridge / 正式 CAD FX source 等遗留项。

Phase 6.9 initial closure and position lifecycle 结果：初始 v0 从数据、回测、paper、
Hummingbot paper/sandbox、首次小资金 live、成交对账、日报、trade/tax export 到冷却复盘的流程
已跑通。当前结果为 `initial_v0_flow_closed_with_warnings`，报告位于
`reports/live_readiness/crypto_relative_strength_v1_phase_6_9_initial_closure_position_plan_low_funds_50/initial_closure_report.md`。

闭环证据完整：Phase 6.7 post-trade 已 reconciled，submitted/filled/db fills 为 `1/1/1`，
余额和风险 cap 检查通过，manual open orders check 为 `confirmed_clean`，已执行过的 one-shot
runner config 已 disarm。下一次 live decision 为 `NO_GO_COOLDOWN_ACTIVE`，原因是 24 小时冷却
窗口尚未结束。当前 BTC 仓位生命周期计划为 `HOLD_UNDER_OBSERVATION`：策略净增
`0.00063936 BTC`，入场 cost basis estimate 为 `49.266880 USDT`，不自动退出；如需退出，
必须单独生成并审批 one-shot sell plan。
