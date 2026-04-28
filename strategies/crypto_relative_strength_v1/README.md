# crypto_relative_strength_v1

BTC/ETH 相对强弱轮动策略，只用于离线研究。

- 信号：计算每个交易对过去 `lookback_window` 根 K 线的收益率。
- 选择：买入收益率最高且不低于 `min_momentum` 的资产。
- 约束：spot only，不做裸空。
- 当前 universe：BTC-USDT、ETH-USDT、BNB-USDT、SOL-USDT、XRP-USDT、ADA-USDT。
- 默认组合：选择 top 2，每个资产最大权重 `25%`，总目标风险暴露 `50%`。

## Phase 3.5 结果

默认全样本回测结果较差：总收益约 `-8.51%`，最大回撤约 `28.22%`，
换手约 `343x`，交易次数 `690`。

walk-forward 网格：

- `lookback_window`: `24,48,72,108,144`
- `min_momentum`: `0,0.02,0.05`
- fee: `0.0006`
- slippage: `2 bps`

结果：正收益折数 `6/10`，平均测试收益约 `2.84%`，中位测试收益约 `2.61%`，
最差测试收益约 `-13.59%`，最差测试回撤约 `14.64%`。

结论：这个方向比 MA baseline 更有研究价值，但尾部风险和换手仍未达标，不能进入
paper trading。

## Phase 3.6 结果

Phase 3.6 扩展到 6 个大流动性 spot 交易对，并扫描：

- `lookback_window`: `24,48,72,108,144`
- `top_n`: `1,2,3`
- `min_momentum`: `0,0.02,0.05`
- fee: `0.0006`
- slippage: `2 bps`

风险约束选择规则：

- `selection_min_return`: `0`
- `selection_max_drawdown`: `0.20`
- `selection_max_turnover`: `45`
- `selection_max_tail_loss`: `0.08`
- score penalty: drawdown `1`，turnover `0.001`，tail loss `2`

结果：正收益折数 `7/10`，平均测试收益约 `10.86%`，中位测试收益约 `4.43%`，
最差测试收益约 `-15.85%`，最差测试回撤约 `23.01%`。

结论：Phase 3.6 是目前最好的研究候选，但最差折亏损和回撤仍偏高。下一步应优先研究
组合级止损、波动率目标仓位和换手约束。

## Phase 3.7 结果

Phase 3.7 增加组合级风险覆盖层：

- realized volatility target: `0.010`
- volatility window: `72`
- global drawdown stop: `10%`
- risk-off cooldown: `36` 根 4h K 线
- per-rebalance turnover cap: `25%`

walk-forward 结果：正收益折数 `7/10`，平均测试收益约 `15.47%`，中位测试收益约
`2.66%`，最差测试收益约 `-4.79%`，最差测试回撤约 `10.62%`。

结论：风险覆盖层显著降低尾部亏损，是目前最接近可运行研究版本的候选。但收益分布仍
不够均匀，paper trading 前需要继续加入容量、成交量参与率和监控恢复流程。

## Phase 3.8 结果

Phase 3.8 增加执行容量约束：

- min order notional: `10 USDT`
- max participation rate: `2%`
- risk recovery bars: `18`

1 万 USDT 研究资金下，walk-forward 收益/回撤与 Phase 3.7 一致，说明容量约束没有
影响当前小资金回测。选中测试折最大观察参与率约 `0.0865%`，最小估算容量约
`23.12` 万 USDT。

100 万 USDT 压力测试触发参与率上限，`participation_capped_count=14`，被截断名义金额
约 `66.84` 万 USDT。结论：当前候选适合小资金 paper trading 研究，但资金规模扩大后
必须启用参与率和容量监控。

## Phase 3.9 结果

Phase 3.9 生成 paper readiness 报告、人工 Markdown 日报和 risk-off 恢复手册。

当前状态：`paper_ready_with_warnings`。

WARN：

- 平均收益受最好测试折影响较大。
- 选中测试折出现 risk-off，需要按恢复手册处理。
- 100 万 USDT 容量压力测试触发参与率上限。

结论：可以进入小资金 paper trading 准备，但必须保留 kill switch、启动前 readiness
检查、每日复核和 risk-off 恢复流程。live trading 继续禁止。

## Phase 4 结果

Phase 4 第一版接入本地 paper cycle，不连接 Hummingbot，不提交真实订单。

smoke run：

- readiness gate: `paper_ready_with_warnings`，通过显式人工允许。
- target weights: `BNB-USDT=0.25`，其他资产为 `0`。
- routed orders: `1`，approved: `1`。
- simulated fill: 买入 `BNB-USDT`，notional `500 USDT`，fee `0.5 USDT`。
- paper account: equity `1999.5 USDT`，gross exposure `500 USDT`。

当前结论：Phase 4 已具备单次本地 paper 下单闭环。下一步应进入 Phase 4.1，把该
cycle 接入定时循环并连续观察 24 小时。

## Phase 4.1 结果

Phase 4.1 已接入本地 paper observation loop。每轮 observation 会记录：

- 账户权益、现金、gross exposure 和持仓。
- 目标权重。
- 风险审批后的订单结果。
- K 线覆盖数量、预期数量和质量状态。

smoke observation：

- cycles: `2`
- status: `ok`
- routed orders: `1`
- approved orders: `1`
- rejected orders: `0`
- market data incomplete cycles: `0`
- last equity: `1999.5 USDT`

当前结论：本地 paper 运行链路、风控审批、ledger 重建和观察报告已跑通。下一步应接入
实时或准实时 K 线刷新，再运行完整 24 小时 observation。

## Phase 4.2 结果

Phase 4.2 已接入准实时 K 线刷新。开启 `--refresh-market-data` 后，observation loop
会在每轮 cycle 前刷新当前 universe 的 Binance spot 已收盘 K 线，并把刷新状态写入
`pre_cycle.market_data_refresh`。

刷新策略：

- 只使用 public K 线接口，不需要交易密钥。
- 默认延迟 `60` 秒确认 K 线收盘。
- 默认重取最近 `2` 根 K 线并 upsert 到 SQLite。
- 刷新失败时，本轮 paper cycle 失败并进入 observation report，不继续生成订单。

当前结论：系统已经具备准实时 paper observation 的数据刷新入口。下一步应启动真实
Binance public data 的 24 小时 observation，并复核刷新状态、数据完整性和风控结果。

public data smoke：

- runtime end: `2026-04-26T00:00:00+00:00`
- latest closed candle: `2026-04-25T20:00:00+00:00`
- per-symbol fetched candles: `692`
- target weights: `BTC-USDT=0.25`，`XRP-USDT=0.25`
- routed orders: `2`
- approved orders: `2`
- rejected orders: `0`
- paper equity: `1999.5 USDT`

## Phase 4.3 结果

Phase 4.3 生成 24 小时 paper observation 复盘报告和 Phase 5 决策门槛。

复盘摘要：

- observation duration: `23.9946` 小时
- cycles: `1397`
- failed cycles: `0`
- market data incomplete cycles: `0`
- refresh failed events: `0`
- rejected orders: `0`
- filled paper orders: `8`
- final equity: `2007.0680 USDT`
- net PnL: `+7.0680 USDT`
- net return: `+0.3534%`
- max drawdown: `0.1887%`
- total fees: `2.0037 USDT`

最终目标仓位：`BTC-USDT=0.25`，`ADA-USDT=0.25`，其他为 `0`。

决策：`sandbox_ready_with_warnings`。

解释：24 小时运行链路通过，但 Phase 3.9 readiness 仍有 WARN，包括收益集中、历史
risk-off 出现和容量压力测试触发参与率上限。因此可以进入 Hummingbot Sandbox 准备，
但 live trading 继续禁止。

## Phase 5 结果

Phase 5 第一版完成 Hummingbot sandbox 准备清单，不调用 Hummingbot API，不提交外部订单。

准备结果：`sandbox_prepared_with_warnings`。

- connector: `binance_paper_trade`
- controller: `quant_system_sandbox_order_controller`
- controller configs: `3`
- sandbox order configs: `8`
- total notional: `2003.6605 USDT`
- submitted orders: `8`
- terminal orders: `8`
- duplicate client ids: `0`
- disconnect/order exception/balance anomaly: `0`

WARN 延续自 Phase 4.3/Phase 3.9 readiness。下一步是把 manifest 加载到 Hummingbot
sandbox/paper mode，采集真实 sandbox 事件并完成订单、成交和余额对账。live trading
继续禁止。

## Phase 5.1 结果

Phase 5.1 增加 Hummingbot sandbox event JSONL 标准化和对账。当前先完成 manifest replay
smoke，尚未连接外部 Hummingbot runtime。

replay 对账结果：`sandbox_reconciled`。

- events: `20`
- submitted: `8`
- filled: `8`
- balance events: `4`
- unknown order ids: `[]`
- missing terminal orders: `[]`
- amount mismatches: `[]`
- balance mismatches: `[]`

下一步需要启动真实 Hummingbot sandbox/paper mode，导出 event JSONL 后复用同一对账入口。
live trading 继续禁止。

## Phase 5.2 结果

Phase 5.2 增加 Hummingbot sandbox session gate，用于启动或延长真实 sandbox/paper session
前的安全门禁。当前仍基于 replay event，不是外部 Hummingbot runtime 实测。

gate 结果：`sandbox_session_ready_with_warnings`。

- `LIVE_TRADING_ENABLED`: `False`
- `GLOBAL_KILL_SWITCH`: `True`
- exchange key env detected: `False`
- expected/submitted/terminal orders: `8/8/8`
- balance events: `4`

WARN：Phase 5 准备报告仍有 readiness warning，且 event source 是 replay。下一步需要用真实
Hummingbot sandbox/paper export 重新运行 Phase 5.1 reconciliation 和 Phase 5.2 gate。

## Phase 5.3 结果

Phase 5.3 生成外部 Hummingbot sandbox/paper dry run 会话包。

package 结果：`sandbox_package_ready_with_warnings`。

- controller configs: `3`
- sandbox orders: `8`
- package output: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_3_session_package`
- 包含：manifest、controller configs、orders JSONL、event schema、event capture template、
  operator runbook 和 package summary。

WARN：该包仍基于 replay gate，只能用于第一次外部 sandbox dry run。真实 Hummingbot event
export 产生后，需要重新运行 Phase 5.1、Phase 5.2 和 Phase 5.3。

## Phase 5.4 结果

Phase 5.4 增加 Hummingbot sandbox event export 一键验收入口。当前使用 replay event 做
smoke，尚未完成外部 Hummingbot runtime 实测。

acceptance 结果：`sandbox_export_accepted_with_warnings`。

- reconciliation: `sandbox_reconciled`
- session gate: `sandbox_session_ready_with_warnings`
- package: `sandbox_package_ready_with_warnings`
- events: `20`
- submitted/terminal orders: `8/8`
- balance events: `4`

下一步需要用真实 Hummingbot sandbox/paper event export 重新运行 Phase 5.4。live trading
继续禁止。

## Phase 5.8 结果

Phase 5.7 已完成真实 Hummingbot CLI direct paper export，Phase 5.8 对该 export 生成更长
observation window 前的准入报告。

结果：`hummingbot_observation_window_ready_with_warnings`。

- event source: `hummingbot_export`
- submitted/filled/terminal: `8/8/8`
- failed/canceled/unknown/missing orders: `0`
- event window: `0.0111` hours，低于目标 `2` hours
- report: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_8_observation_review.md`

WARN 继续来自短窗口、XRP paper 可用余额裁剪、fill price drift、fee drift 和 balance
reconciliation skipped。下一步可以准备更长 Hummingbot CLI direct paper observation window，
但必须先从最新批准的 paper ledger 重新生成 manifest。live trading 继续禁止。

## Phase 5.9 结果

Phase 5.9 给 Hummingbot CLI direct paper script 增加 observation window 能力，并完成 `120`
秒 smoke。

结果：

- acceptance: `sandbox_export_accepted_with_warnings`
- observation review: `hummingbot_observation_window_ready_with_warnings`
- events: `85`
- submitted/filled: `8/8`
- heartbeat/balance/session_completed: `9/58/1`
- failed/canceled/unknown/missing orders: `0`

当前 direct paper 已能写出 heartbeat、periodic balance、final balance 和 session completion。
下一步可以把最短运行时长提高到 `7200` 秒做 2 小时 Hummingbot paper observation。live trading
继续禁止。

## Phase 5.10 结果

Phase 5.10 完成 `7200` 秒 Hummingbot CLI direct paper observation，并用 r2 事件文件重跑
export acceptance 与 observation review。

结果：

- acceptance: `sandbox_export_accepted_with_warnings`
- observation review: `hummingbot_observation_window_ready_with_warnings`
- events: `397`
- submitted/filled/terminal: `8/8/8`
- heartbeat/balance/session_completed: `121/258/1`
- failed/canceled/unknown/missing orders: `0`
- report: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.md`

WARN 继续来自 Hummingbot paper 可用余额裁剪、fill price drift、fee drift 和 balance
reconciliation skipped。该结果允许进入 Phase 6 的只读 live readiness preflight，但不代表可以
直接提交真实订单。

## Phase 6.1 结果

Phase 6.1 新增 Hummingbot daily report 和 live readiness preflight。当前结果：

- daily report: `daily_report_ready_with_warnings`
- live readiness: `live_preflight_ready_with_warnings`
- live trading enabled: `False`
- global kill switch: `True`
- Hummingbot API configured: `True`
- exchange key env detected in current shell: `False`

报告：

- `reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.md`
- `reports/live_readiness/crypto_relative_strength_v1_phase_6_1_live_readiness.md`

Phase 6.2 已配置并验证 Telegram 外部告警通道，并生成更严格的 live risk 配置。live trading
继续保持禁用。

## Phase 6.2 结果

Phase 6.2 生成首次小资金实盘前的 activation checklist、严格 live risk 配置和 trade/tax
export 验证。

严格 live risk 配置：

- `strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml`
- max order notional: `250`
- max symbol notional: `500`
- max gross notional: `1000`
- max daily loss: `50`
- max drawdown: `0.05`

Trade/tax export：

- CSV: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export.csv`
- summary: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export_summary.md`
- rows: `8`
- status: `tax_export_ready_with_warnings`

Activation checklist：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.md`
- decision: `live_activation_ready`

已通过自动项：Phase 6.1 readiness、daily report、tax export、严格 live risk cap、
`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`、Telegram 外部告警通道。

人工确认项已完成：凭据权限范围、交易所 allowlist、操作员 activation signoff。继续禁止 live
trading；下一步 Phase 6.3 才准备真实 live connector handoff。

## Phase 6.3 结果

Phase 6.3 增加 Hummingbot live connector 配置交接和预检。当前结果：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.md`
- decision: `live_connector_preflight_ready`
- expected connector: `binance`
- market type: `spot`
- first live allowlist: `BTC-USDT`, `ETH-USDT`
- host connector path: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors/binance.yml`

已通过项：Phase 6.2 activation、凭据权限/allowlist、操作员 signoff、严格 live risk、
`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`、外部告警通道、交易所 key 未放入
`quant-system` 环境变量、Hummingbot `binance` connector 文件存在、必需 secret 字段名存在。

报告只检查 `binance_api_key`、`binance_api_secret` 字段名，不输出密钥值。下一步进入首次
小资金 live batch activation plan；live trading 继续禁止，直到单独 activation。

## Phase 6.4 结果

Phase 6.4 生成首次小资金 live batch activation plan。当前结果：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan_low_funds_50.md`
- decision: `live_batch_activation_plan_approved`
- batch id: `crypto_relative_strength_v1_first_live_batch_001_low_funds_50`
- connector: `binance`
- market type: `spot`
- allowlist: `BTC-USDT`, `ETH-USDT`
- max batch orders: `1`
- max batch notional: `50 USDT`
- max order notional: `50 USDT`
- live order submission armed: `False`

已通过项：Phase 6.3 preflight、BTC/ETH allowlist、严格 live risk、`LIVE_TRADING_ENABLED=false`、
`GLOBAL_KILL_SWITCH=true`、外部告警和密钥隔离。

operator final go 已确认，但本阶段没有生成 live runner，`live_order_submission_armed=False`。

## Phase 6.5 结果

Phase 6.5 刷新 BTC/ETH public market data，并生成候选 live batch package。当前结果：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/package.md`
- decision: `live_batch_execution_package_ready_pending_exchange_state_check`
- execution runner generated: `False`
- live order submission armed: `False`
- candidate orders: `1`

候选订单：

- pair: `BTC-USDT`
- side: `buy`
- order type: `market`
- estimated notional: `50 USDT`
- estimated price: `77371.32000000`
- estimated quantity: `0.0006462342893981904405921987631`
- signal timestamp: `2026-04-27T20:00:00+00:00`

操作员已确认低资金版 exchange state check：Binance spot 可用 USDT 足够覆盖 `50 USDT`
买入和手续费、当前没有异常 open orders，且当前 BTC/ETH/USDT 持仓不会让本批次超过风险上限。

## Phase 6.6 结果

Phase 6.6 基于低资金版候选订单生成一次性 Hummingbot live runner。当前结果：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.md`
- decision: `live_one_batch_runner_ready`
- session id: `crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50`
- script config: `crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`
- installed script: `/Users/albertlz/Downloads/private_proj/hummingbot/scripts/quant_system_live_one_batch.py`
- installed config: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/scripts/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`
- event log: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`
- live order submission armed: `True`
- exchange state confirmed: `True`

该 runner 已在人工确认后启动并完成首次低资金 live batch；完成后一次性 runner 容器已停止。

## Phase 6.7 结果

Phase 6.7 对首次真实成交生成 post-trade reconciliation、daily report 和 trade/tax export。
当前结果：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.md`
- daily report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/daily_report.md`
- trade/tax export: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/trade_tax_export.csv`
- status: `live_post_trade_reconciled_with_warnings`
- submitted / filled / DB fills: `1 / 1 / 1`
- trading pair: `BTC-USDT`
- side: `buy`
- order type: `market`
- gross quote notional: `49.266880 USDT`
- average fill price: `76979.5 USDT`
- gross base quantity: `0.00064 BTC`
- fee: `0.00000064 BTC`
- net base quantity: `0.00063936 BTC`
- balance deltas: `USDT -49.26688000`, `BTC +0.00063936`

对账结果：无 missing submissions、无 missing fills、无 DB fill mismatch、无余额 mismatch；
名义金额、order count、allowlist 和 price deviation 均在低资金 cap 内。WARN 来自 MQTT bridge
未连接，以及 tax export 仍使用 `validation_only_not_tax_filing`，不能作为最终报税文件。

## Phase 6.8 结果

Phase 6.8 进入首次 live batch 后的冷却复盘。当前结果：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/cooldown_review.md`
- status: `live_cooldown_active_with_warnings`
- cooldown completed at: `2026-04-28T02:34:33.175500+00:00`
- minimum cooldown hours: `24`
- next review not before: `2026-04-29T02:34:33.175500+00:00`
- event log last event: `session_completed`
- event log lines: `3022`
- one-shot runner container: `not_found`
- installed runner config armed: `False`
- manual open orders check: `confirmed_clean`
- expansion allowed: `False`

Phase 6.8 不允许新增 live batch、不允许扩大交易对、不允许提高 `50 USDT` 低资金 cap。
操作员已完成 Binance open orders 人工检查，未发现异常 open orders。冷却期内只做复盘，并处理
MQTT bridge 和正式 CAD FX source 等遗留项。

## Phase 6.9 结果

Phase 6.9 生成初始版本闭环判定和 BTC 小仓位生命周期计划。当前结果：

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_9_initial_closure_position_plan_low_funds_50/initial_closure_report.md`
- status: `initial_v0_flow_closed_with_warnings`
- initial flow closed: `True`
- evidence complete: `True`
- next live decision: `NO_GO_COOLDOWN_ACTIVE`
- position stance: `HOLD_UNDER_OBSERVATION`
- strategy net BTC quantity: `0.00063936`
- entry cost basis quote: `49.266880 USDT`
- account ending BTC balance: `0.00074442`
- exit requires activation: `True`

结论：初始版本流程已跑通，但冷却期未满，不能启动下一次 live batch。当前 BTC 小仓位只观察，
不自动退出；如果后续要退出，必须单独生成并审批 one-shot sell plan。
