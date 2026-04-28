# Quant System

一套面向加密市场的机构级量化交易系统。系统把 Hummingbot 定位为执行基础设施：
连接交易所、订阅行情、维护订单状态、处理精度和复用 Strategy V2 Executor。自研部分负责
alpha、组合、账户级风控、回测研究、实验追踪、监控和报表。

## 当前阶段

Phase 6.9: initial v0 flow closed, next live batch blocked by cooldown。

- 真实 API key 只允许配置在 Hummingbot CLI connector 中。
- 不在 `quant-system/.env` 存放交易所 API key。
- 首次低资金 live batch 已执行：`BTC-USDT` market buy，`1` 笔。
- 成交 gross notional `49.266880 USDT`，gross `0.00064 BTC`，net `0.00063936 BTC`。
- Phase 6.7 已完成 reconciliation、daily report 和 trade/tax export。
- Phase 6.8 已进入 24 小时冷却复盘，下一次 review 不早于 `2026-04-29T02:34:33.175500+00:00`。
- 已执行过的 Hummingbot one-shot runner config 已 disarm：`live_order_submission_armed=false`。
- Phase 6.9 判定初始 v0 流程已闭环，当前下一次 live decision 为 `NO_GO_COOLDOWN_ACTIVE`。
- `quant-system` 默认仍保持 `LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`；不得自动扩大交易对或额度。

## 模块边界

Hummingbot 直接承担：

- exchange connector
- WebSocket 行情
- 订单创建、撤销、状态追踪
- 余额、持仓、交易对精度和最小下单量
- PositionExecutor、TWAPExecutor、Grid/DCA/XEMM/Arbitrage Executor
- Docker、Dashboard、API

本系统自研：

- 策略信号和交易过滤
- 多策略、多币种、多账户组合管理
- 账户级全局风控和 kill switch
- 回测、数据仓库、实验记录
- 交易日志分析、风险 dashboard、监控告警
- 加拿大税务/报表导出基础数据

## 本地验证

```bash
./venv/bin/python main.py
./venv/bin/python -m unittest discover -s tests
```

## Phase 2 数据导入示例

```bash
./venv/bin/python -m packages.data.import_candles \
  --input data/samples/binance_1h_candles.csv \
  --quality-report /tmp/quant-system-data-quality.json
```

## Phase 2.1 Binance 历史 K 线下载

```bash
./venv/bin/python -m packages.data.download_binance_candles \
  --symbols BTC-USDT ETH-USDT \
  --interval 4h \
  --start 2025-01-01 \
  --end 2026-01-01 \
  --output data/raw/binance_spot_BTC-ETH_4h_2025.csv \
  --quality-report data/reports/binance_spot_BTC-ETH_4h_2025_quality.json
```

如果本机 Python 证书链被本地代理或系统 CA 配置影响，且只下载 public market data，可以临时追加
`--insecure-skip-tls-verify`。

## Phase 2.2 SQLite 数据仓库

```bash
./venv/bin/python -m packages.data.load_candles_sqlite \
  --input data/raw/binance_spot_BTC-ETH_4h_2025.csv \
  --db data/warehouse/quant_system.sqlite \
  --quality-report data/reports/binance_spot_BTC-ETH_4h_2025_sqlite_load_quality.json
```

## Phase 2.3 策略数据查询

```bash
./venv/bin/python -m packages.data.query_strategy_candles \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite
```

## Phase 3 回测

```bash
./venv/bin/python -m packages.backtesting.run_backtest \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite \
  --output reports/backtests/crypto_momentum_v1_2025.json
```

## Phase 3.1 参数扫描

```bash
./venv/bin/python -m packages.backtesting.run_parameter_scan \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite \
  --fast-windows 12,24,36 \
  --slow-windows 72,96,144 \
  --fee-rates 0.0006,0.001 \
  --slippage-bps 2,5 \
  --output reports/backtests/crypto_momentum_v1_phase_3_1_scan.json \
  --summary-csv reports/backtests/crypto_momentum_v1_phase_3_1_scan.csv
```

## Phase 3.2 Train/Test 验证

```bash
./venv/bin/python -m packages.backtesting.run_train_test_validation \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite \
  --train-start 2025-01-01 \
  --train-end 2025-07-01 \
  --test-start 2025-07-01 \
  --test-end 2026-01-01 \
  --fast-windows 12,24,36 \
  --slow-windows 72,96,144 \
  --fee-rates 0.0006,0.001 \
  --slippage-bps 2,5 \
  --output reports/backtests/crypto_momentum_v1_phase_3_2_train_test.json \
  --summary-csv reports/backtests/crypto_momentum_v1_phase_3_2_train_test.csv
```

## Phase 3.3 Walk-Forward 验证

```bash
./venv/bin/python -m packages.backtesting.run_walk_forward \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --train-months 6 \
  --test-months 3 \
  --step-months 3 \
  --fast-windows 12,24,36 \
  --slow-windows 72,96,144 \
  --fee-rates 0.0006,0.001 \
  --slippage-bps 2,5 \
  --output reports/backtests/crypto_momentum_v1_phase_3_3_walk_forward.json \
  --summary-csv reports/backtests/crypto_momentum_v1_phase_3_3_walk_forward.csv
```

## Phase 3.4 市场状态过滤

```bash
./venv/bin/python -m packages.backtesting.run_walk_forward \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite \
  --experiment-id crypto_momentum_v1_phase_3_4 \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --train-months 6 \
  --test-months 3 \
  --step-months 3 \
  --fast-windows 12,24,36 \
  --slow-windows 72,96,144 \
  --fee-rates 0.0006 \
  --slippage-bps 2 \
  --min-trend-strengths 0,0.003,0.006 \
  --max-volatility none,0.04 \
  --output reports/backtests/crypto_momentum_v1_phase_3_4_regime_filter_walk_forward.json \
  --summary-csv reports/backtests/crypto_momentum_v1_phase_3_4_regime_filter_walk_forward.csv
```

## Phase 3.5 相对强弱轮动

```bash
./venv/bin/python -m packages.backtesting.run_walk_forward \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --experiment-id crypto_relative_strength_v1_phase_3_5 \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --train-months 6 \
  --test-months 3 \
  --step-months 3 \
  --lookback-windows 24,48,72,108,144 \
  --min-momentum 0,0.02,0.05 \
  --fee-rates 0.0006 \
  --slippage-bps 2 \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_5_walk_forward.json \
  --summary-csv reports/backtests/crypto_relative_strength_v1_phase_3_5_walk_forward.csv
```

Phase 3.5 增加了 `crypto_relative_strength_v1`，用于验证 BTC/ETH 相对强弱轮动。
这版 walk-forward 正收益折数为 `6/10`，中位测试收益约 `2.61%`，但最差测试收益约
`-13.59%`，仍只能作为研究候选，不能进入 paper trading。

## Phase 3.6 多币种相对强弱与风险约束选择

```bash
./venv/bin/python -m packages.backtesting.run_walk_forward \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --experiment-id crypto_relative_strength_v1_phase_3_6_largecap_risk_adjusted \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --train-months 6 \
  --test-months 3 \
  --step-months 3 \
  --lookback-windows 24,48,72,108,144 \
  --rotation-top-n-values 1,2,3 \
  --min-momentum 0,0.02,0.05 \
  --fee-rates 0.0006 \
  --slippage-bps 2 \
  --selection-mode risk_adjusted \
  --selection-min-return 0 \
  --selection-max-drawdown 0.20 \
  --selection-max-turnover 45 \
  --selection-max-tail-loss 0.08 \
  --drawdown-penalty 1 \
  --turnover-penalty 0.001 \
  --tail-loss-penalty 2 \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_6_largecap_risk_adjusted_walk_forward.json \
  --summary-csv reports/backtests/crypto_relative_strength_v1_phase_3_6_largecap_risk_adjusted_walk_forward.csv
```

Phase 3.6 把相对强弱 universe 扩到 `BTC`、`ETH`、`BNB`、`SOL`、`XRP`、`ADA`，
并加入 `risk_adjusted` 参数选择模式。该模式先按训练集风险约束筛选，再用收益减去
回撤、换手和单 bar tail loss 惩罚后的分数排名。

当前最佳 Phase 3.6 walk-forward：正收益折数 `7/10`，平均测试收益约 `10.86%`，
中位测试收益约 `4.43%`，最差测试收益约 `-15.85%`，最差测试回撤约 `23.01%`。
相比 Phase 3.5 有明显改善，但尾部风险仍不满足 paper trading 标准。

## Phase 3.7 风险覆盖层

Phase 3.7 不改 alpha 信号，而是在组合层加入三类风控：

- 波动率目标：按最近 `72` 根 4h K 线的组合 realized volatility 缩放风险暴露。
- 全局高水位熔断：组合从高水位回撤超过 `10%` 后进入 risk-off 冷却。
- 单次换手上限：每次调仓交易额不超过权益的 `25%`。

```bash
./venv/bin/python -m packages.backtesting.run_walk_forward \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --experiment-id crypto_relative_strength_v1_phase_3_7_risk_overlay \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --train-months 6 \
  --test-months 3 \
  --step-months 3 \
  --lookback-windows 24,48,72,108,144 \
  --rotation-top-n-values 1,2,3 \
  --min-momentum 0,0.02,0.05 \
  --fee-rates 0.0006 \
  --slippage-bps 2 \
  --selection-mode risk_adjusted \
  --selection-min-return 0 \
  --selection-max-drawdown 0.20 \
  --selection-max-turnover 45 \
  --selection-max-tail-loss 0.08 \
  --drawdown-penalty 1 \
  --turnover-penalty 0.001 \
  --tail-loss-penalty 2 \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_7_risk_overlay_walk_forward.json \
  --summary-csv reports/backtests/crypto_relative_strength_v1_phase_3_7_risk_overlay_walk_forward.csv
```

Phase 3.7 walk-forward：正收益折数 `7/10`，平均测试收益约 `15.47%`，
中位测试收益约 `2.66%`，最差测试收益约 `-4.79%`，最差测试回撤约 `10.62%`。
尾部风险比 Phase 3.6 明显收敛，但收益分布仍依赖少数强趋势测试折。

## Phase 3.8 执行容量约束

Phase 3.8 在回测执行层加入更接近真实交易的约束：

- `min_order_notional`: 最小下单额，低于该金额的订单跳过。
- `max_participation_rate`: 单笔订单不超过当前 K 线成交额的一定比例。
- `estimated_participation_capacity_equity`: 按观测最大参与率估算当前参与率上限下的容量。
- `risk_recovery_bars`: risk-off 冷却后的风险恢复窗口。

```bash
./venv/bin/python -m packages.backtesting.run_walk_forward \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --experiment-id crypto_relative_strength_v1_phase_3_8_execution_constraints \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --train-months 6 \
  --test-months 3 \
  --step-months 3 \
  --lookback-windows 24,48,72,108,144 \
  --rotation-top-n-values 1,2,3 \
  --min-momentum 0,0.02,0.05 \
  --fee-rates 0.0006 \
  --slippage-bps 2 \
  --selection-mode risk_adjusted \
  --selection-min-return 0 \
  --selection-max-drawdown 0.20 \
  --selection-max-turnover 45 \
  --selection-max-tail-loss 0.08 \
  --drawdown-penalty 1 \
  --turnover-penalty 0.001 \
  --tail-loss-penalty 2 \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_walk_forward.json \
  --summary-csv reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_walk_forward.csv
```

当前 1 万 USDT 研究资金下，Phase 3.8 walk-forward 与 Phase 3.7 的收益/回撤一致：
正收益折数 `7/10`，平均测试收益约 `15.47%`，最差测试收益约 `-4.79%`。
执行约束没有截断选中测试折的订单，最小估算容量约 `23.12` 万 USDT。100 万 USDT
容量压力测试会触发参与率上限，说明容量约束已生效。

## Phase 3.9 Paper Readiness

Phase 3.9 把 Phase 3.8 的 walk-forward 和容量压力测试转成 paper trading 前检查：

```bash
./venv/bin/python -m packages.reporting.run_paper_readiness_report \
  --walk-forward-json reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_walk_forward.json \
  --capacity-stress-json reports/backtests/crypto_relative_strength_v1_phase_3_8_capacity_stress_1m.json \
  --output-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --output-md reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_daily_report.md \
  --runbook-md reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_risk_off_runbook.md
```

当前状态：`paper_ready_with_warnings`。没有 CRITICAL 阻断，但有三个 WARN：
收益集中、测试折出现 risk-off、100 万 USDT 压力测试触发容量上限。结论是可以进入
小资金 paper trading 准备，但 live trading 继续禁止。

## Phase 4 Paper Trading

Phase 4 第一版只做本地 paper cycle：读取 SQLite K 线，按
`crypto_relative_strength_v1` 生成目标权重，通过风险引擎审批，然后把模拟成交写入
JSONL ledger。它不连接 Hummingbot，不会提交真实订单。

```bash
./venv/bin/python -m packages.paper_trading.run_paper_cycle \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --readiness-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --allow-readiness-warnings \
  --ledger reports/paper_trading/crypto_relative_strength_v1_phase_4_paper_ledger.jsonl \
  --summary reports/paper_trading/crypto_relative_strength_v1_phase_4_cycle_summary.json \
  --account-id paper-main \
  --initial-equity 2000
```

本次 Phase 4 smoke run 结果：

- readiness gate: `paper_ready_with_warnings`，通过人工允许参数进入 paper。
- orders: `1`，approved: `1`。
- simulated fill: 买入 `BNB-USDT`，notional `500 USDT`。
- fee: `0.5 USDT`，paper equity: `1999.5 USDT`。

如需手动阻断新订单，可给 runner 传入 kill switch JSON：

```json
{"active": true, "reason": "manual stop"}
```

并追加参数 `--kill-switch-file <path>`。kill switch 激活时订单意图会被风险引擎拒绝，
不会写入成交 ledger。

## Phase 4.1 Paper Observation Loop

Phase 4.1 把单次 paper cycle 接入定时循环，并为每轮生成观察记录：

```bash
./venv/bin/python -m packages.paper_trading.run_paper_observation \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --readiness-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --allow-readiness-warnings \
  --ledger reports/paper_trading/crypto_relative_strength_v1_phase_4_1_paper_ledger.jsonl \
  --observation-log reports/paper_trading/crypto_relative_strength_v1_phase_4_1_observation.jsonl \
  --summary-json reports/paper_trading/crypto_relative_strength_v1_phase_4_1_summary.json \
  --report-md reports/paper_trading/crypto_relative_strength_v1_phase_4_1_report.md \
  --account-id paper-main \
  --initial-equity 2000 \
  --cycles 2 \
  --interval-seconds 0
```

24 小时观察时使用 `--duration-hours 24 --interval-seconds 60`，可不传 `--cycles`。

本次 Phase 4.1 smoke observation：

- status: `ok`
- cycles: `2`
- routed orders: `1`，approved: `1`，rejected: `0`
- market data incomplete cycles: `0`
- last equity: `1999.5 USDT`

## Phase 4.2 Market Data Refresh

Phase 4.2 在 observation loop 前增加准实时 K 线刷新。开启
`--refresh-market-data` 后，每轮会：

1. 读取 SQLite 中每个交易对的最新 K 线。
2. 只拉取 Binance spot 已收盘 K 线，默认延迟 `60` 秒确认收盘。
3. re-fetch 最近 `2` 根 K 线并 upsert，修正可能的尾部更新。
4. 用最新已收盘 K 线时间作为 runtime query end，再运行 paper cycle。

```bash
./venv/bin/python -m packages.paper_trading.run_paper_observation \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --readiness-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --allow-readiness-warnings \
  --ledger reports/paper_trading/crypto_relative_strength_v1_phase_4_2_ledger.jsonl \
  --observation-log reports/paper_trading/crypto_relative_strength_v1_phase_4_2_observation.jsonl \
  --summary-json reports/paper_trading/crypto_relative_strength_v1_phase_4_2_summary.json \
  --report-md reports/paper_trading/crypto_relative_strength_v1_phase_4_2_report.md \
  --account-id paper-main \
  --initial-equity 2000 \
  --refresh-market-data \
  --duration-hours 24 \
  --interval-seconds 60
```

当前实现仍只使用 Binance public market data 和本地 paper execution，不连接 Hummingbot，
不提交真实订单。

本次 Phase 4.2 public data smoke：

- refresh status: `ok`
- runtime end: `2026-04-26T00:00:00+00:00`
- latest closed candle: `2026-04-25T20:00:00+00:00`
- fetched candles: 每个交易对 `692` 根 4h K 线
- market data complete cycles: `1/1`
- target weights: `BTC-USDT=0.25`，`XRP-USDT=0.25`
- routed orders: `2`，approved: `2`，rejected: `0`
- paper equity: `1999.5 USDT`

## Phase 4.3 Observation Review

Phase 4.3 把 24 小时 paper observation 转成进入 Phase 5 前的复盘和决策门槛：

```bash
./venv/bin/python -m packages.reporting.run_paper_observation_review \
  --observation-jsonl reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_observation.jsonl \
  --ledger-jsonl reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_ledger.jsonl \
  --readiness-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --initial-equity 2000 \
  --output-json reports/paper_trading/crypto_relative_strength_v1_phase_4_3_observation_review.json \
  --output-md reports/paper_trading/crypto_relative_strength_v1_phase_4_3_observation_review.md
```

当前决策：`sandbox_ready_with_warnings`。

24 小时复盘结果：

- cycles: `1397`
- failed cycles: `0`
- market data incomplete cycles: `0`
- refresh failed events: `0`
- rejected orders: `0`
- net PnL: `+7.0680 USDT`
- net return: `+0.3534%`
- max drawdown: `0.1887%`
- total fees: `2.0037 USDT`

WARN 来自 Phase 3.9 readiness：收益集中、risk-off 历史出现、100 万 USDT 容量压力测试触发
参与率上限。因此下一步只允许进入 Hummingbot Sandbox 准备，live trading 继续禁止。

## Phase 5 Hummingbot Sandbox Preparation

Phase 5 第一步把 Phase 4.3 复盘和 paper ledger 转成 Hummingbot sandbox manifest，
并在本地模拟订单生命周期检查。该步骤仍不调用 Hummingbot API，不配置真实交易所密钥，
不允许 live trading。

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_prepare \
  --review-json reports/paper_trading/crypto_relative_strength_v1_phase_4_3_observation_review.json \
  --ledger-jsonl reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_ledger.jsonl \
  --allow-warnings \
  --connector-name binance_paper_trade \
  --controller-name quant_system_sandbox_order_controller \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --report-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_prepare.json \
  --report-md reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_prepare.md
```

当前 Phase 5 准备结果：`sandbox_prepared_with_warnings`。

- controller configs: `3`
- sandbox order configs: `8`
- total notional: `2003.6605 USDT`
- submitted orders: `8`
- terminal orders: `8`
- duplicate client ids: `0`
- disconnect/order exception/balance anomaly: `0`

WARN 继续来自 Phase 4.3/Phase 3.9 readiness。下一步 Phase 5.1 才能把该 manifest
接入真实 Hummingbot sandbox/paper mode，采集 submitted、filled、canceled、failed、
disconnect 和 balance 事件，并做订单/余额对账。live trading 仍然禁止。

## Phase 5.1 Sandbox Event Reconciliation

Phase 5.1 增加 Hummingbot sandbox 事件接入和对账层。它可以读取 Hummingbot sandbox/paper
mode 导出的 JSONL 事件，也可以先用 Phase 5 manifest 做本地 replay smoke，验证对账逻辑。

本地 replay smoke：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_reconciliation \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --replay-from-manifest \
  --starting-quote-balance 2000 \
  --quote-asset USDT \
  --output-events-jsonl reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_1_sandbox_events.jsonl \
  --output-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_1_reconciliation.json \
  --output-md reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_1_reconciliation.md
```

接入真实 Hummingbot sandbox/paper event export 时，把 `--replay-from-manifest` 换成
`--events-jsonl <hummingbot_events.jsonl>`。

当前 Phase 5.1 replay 结果：`sandbox_reconciled`。

- events: `20`
- submitted: `8`
- filled: `8`
- balance events: `4`
- unknown order ids: `[]`
- missing terminal orders: `[]`
- balance mismatches: `[]`

该结果只证明事件标准化和对账逻辑已跑通，还不是外部 Hummingbot runtime 实测。

## Phase 5.2 Sandbox Session Gate

Phase 5.2 增加真实 Hummingbot sandbox/paper session 启动前门禁。它汇总 Phase 5 manifest、
Phase 5 准备报告、Phase 5.1 对账报告和当前安全环境，判断是否可以启动外部 sandbox
session。该步骤仍不启动 Hummingbot，不读取交易所密钥，不提交订单。

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_session_gate \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --prepare-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_prepare.json \
  --reconciliation-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_1_reconciliation.json \
  --event-jsonl reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_1_sandbox_events.jsonl \
  --session-id crypto_relative_strength_v1_phase_5_2_replay_gate \
  --event-source replay \
  --allow-warnings \
  --output-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_2_sandbox_session_gate.json \
  --output-md reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_2_sandbox_session_gate.md
```

当前 Phase 5.2 gate 结果：`sandbox_session_ready_with_warnings`。

- `LIVE_TRADING_ENABLED`: `False`
- `GLOBAL_KILL_SWITCH`: `True`
- exchange key env detected: `False`
- expected/submitted/terminal orders: `8/8/8`
- balance events: `4`

WARN：Phase 5 准备报告仍有 readiness warning，且当前事件来源是 replay。下一步需要用真实
Hummingbot sandbox/paper event export 重新运行 Phase 5.1 reconciliation 和 Phase 5.2 gate。

## Phase 5.3 Sandbox Handoff Package

Phase 5.3 把 manifest 和 session gate 汇总成一个外部 Hummingbot sandbox/paper dry run
会话包。它只导出文件，不启动 Hummingbot，不连接 API，不提交订单。

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_package \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --session-gate-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_2_sandbox_session_gate.json \
  --output-dir reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_3_session_package \
  --allow-warnings
```

当前 Phase 5.3 package 结果：`sandbox_package_ready_with_warnings`。

输出目录：`reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_3_session_package`

- `manifest.json`
- `controller_configs.json`
- `controller_configs/ada_usdt.json`
- `controller_configs/btc_usdt.json`
- `controller_configs/xrp_usdt.json`
- `orders.jsonl`
- `expected_event_schema.json`
- `event_capture_template.jsonl`
- `operator_runbook.md`
- `package_summary.json`
- `package_summary.md`

WARN：该包仍基于 replay gate，只能用于第一次外部 sandbox dry run。真实 Hummingbot event
export 产生后，必须重新跑 Phase 5.1、Phase 5.2 和 Phase 5.3。

## Phase 5.4 Sandbox Export Acceptance

Phase 5.4 增加 sandbox event export 的一键验收入口。给它一个 Hummingbot event JSONL 后，
它会连续执行 Phase 5.1 reconciliation、Phase 5.2 session gate 和 Phase 5.3 package
regeneration。当前先用 replay event 做 smoke，不代表真实 Hummingbot runtime 已经跑过。

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_export_acceptance \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --prepare-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_prepare.json \
  --events-jsonl reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_1_sandbox_events.jsonl \
  --output-dir reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_4_export_acceptance \
  --session-id crypto_relative_strength_v1_phase_5_4_replay_acceptance \
  --event-source replay \
  --starting-quote-balance 2000 \
  --quote-asset USDT \
  --allow-warnings
```

当前 Phase 5.4 replay acceptance 结果：`sandbox_export_accepted_with_warnings`。

- reconciliation: `sandbox_reconciled`
- session gate: `sandbox_session_ready_with_warnings`
- package: `sandbox_package_ready_with_warnings`
- events: `20`
- submitted/terminal orders: `8/8`
- balance events: `4`

真实 Hummingbot dry run 后，把 `--events-jsonl` 指向真实导出的文件，并把
`--event-source replay` 改为 `--event-source hummingbot_export`。

Phase 5.7 已完成真实 Hummingbot CLI paper export acceptance：

- decision: `sandbox_export_accepted_with_warnings`
- events: `26`
- submitted/filled/balance: `8/8/10`
- failed/canceled/unknown/missing orders: `0`
- event JSONL: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_7_hummingbot_events.jsonl`

WARN 来自 Hummingbot paper 运行事实：1 笔 XRP 卖单因 paper 可用余额裁剪，实时 fill 价格
和手续费相对 manifest 估算有偏移，余额数量核对因 Hummingbot paper 默认资产与 Phase 4
本地账户不同而跳过。live trading 仍然禁止。

## Phase 5.8 Hummingbot Observation Window Gate

Phase 5.8 把 Phase 5.7 的真实 Hummingbot export 转成进入更长 observation window 前的准入报告：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_observation_review \
  --acceptance-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_7_export_acceptance/acceptance.json \
  --events-jsonl /Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_7_hummingbot_events.jsonl \
  --session-id crypto_relative_strength_v1_phase_5_8_observation_gate \
  --target-window-hours 2 \
  --allow-warnings \
  --output-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_8_observation_review.json \
  --output-md reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_8_observation_review.md
```

当前结果：`hummingbot_observation_window_ready_with_warnings`。

- submitted/filled/terminal: `8/8/8`
- failed/canceled/unknown/missing orders: `0`
- event window: `0.0111` hours，低于目标 `2` hours
- report: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_8_observation_review.md`

该结果允许准备更长 Hummingbot CLI direct paper observation window，但不允许盲目重复提交旧
manifest。下一轮需要先用最新批准的 paper ledger 重新生成 manifest。live trading 继续禁止。

## Phase 5.9 Hummingbot Observation Smoke

Phase 5.9 给 direct paper script 增加最短运行时长、heartbeat、周期余额快照、final balance
snapshot 和 `session_completed` 事件，并完成 120 秒 smoke。

当前结果：

- acceptance: `sandbox_export_accepted_with_warnings`
- observation review: `hummingbot_observation_window_ready_with_warnings`
- event JSONL: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_9_hummingbot_events.jsonl`
- events: `85`
- submitted/filled: `8/8`
- heartbeat/balance/session_completed: `9/58/1`
- failed/canceled/unknown/missing orders: `0`

这证明 direct paper 已能支撑窗口化 observation。下一轮可以把最短运行时长提高到 `7200` 秒做
2 小时观察。live trading 继续禁止。

## Phase 5.10 Hummingbot 2h Observation

Phase 5.10 已完成 `7200` 秒 Hummingbot CLI direct paper observation，并在结束后重新运行
export acceptance 和 observation review。

当前结果：

- acceptance: `sandbox_export_accepted_with_warnings`
- observation review: `hummingbot_observation_window_ready_with_warnings`
- event JSONL: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_10_r2_hummingbot_events.jsonl`
- events: `397`
- submitted/filled/terminal: `8/8/8`
- heartbeat/balance/session_completed: `121/258/1`
- failed/canceled/unknown/missing orders: `0`
- report: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.md`

WARN 继续来自 Hummingbot paper 的 XRP 可用余额裁剪、实时 fill price drift、fee drift，以及
多资产 paper 初始余额无法用单一 quote 起始余额完整核对。live trading 仍然禁止。

## Phase 6.1 Live Readiness Preflight

Phase 6.1 增加实盘前只读门禁和 Hummingbot 日报样例。该步骤不会启用实盘，也不会读取或打印
交易所密钥值。

```bash
./venv/bin/python -m packages.reporting.run_hummingbot_daily_report \
  --events-jsonl /Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_10_r2_hummingbot_events.jsonl \
  --observation-review-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.json \
  --session-id crypto_relative_strength_v1_phase_6_1_daily_report \
  --strategy-id crypto_relative_strength_v1 \
  --quote-asset USDT \
  --output-json reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.json \
  --output-md reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.md
```

```bash
HUMMINGBOT_API_BASE_URL=http://127.0.0.1:8000 ./venv/bin/python -m packages.reporting.run_live_readiness \
  --observation-review-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.json \
  --acceptance-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_export_acceptance/acceptance.json \
  --daily-report-json reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.json \
  --risk-yml strategies/crypto_relative_strength_v1/risk.yml \
  --session-id crypto_relative_strength_v1_phase_6_1_live_readiness \
  --strategy-id crypto_relative_strength_v1 \
  --allow-warnings \
  --min-observation-hours 2 \
  --max-initial-live-order-notional 250 \
  --live-trading-enabled false \
  --global-kill-switch true \
  --output-json reports/live_readiness/crypto_relative_strength_v1_phase_6_1_live_readiness.json \
  --output-md reports/live_readiness/crypto_relative_strength_v1_phase_6_1_live_readiness.md
```

当前结果：`live_preflight_ready_with_warnings`。

- 2 小时 Hummingbot paper observation 通过。
- Hummingbot 日报生成成功，状态为 `daily_report_ready_with_warnings`。
- `LIVE_TRADING_ENABLED=false`，`GLOBAL_KILL_SWITCH=true`。
- 当前 shell 未检测到交易所 key 环境变量。
- Phase 6.2 已验证 Telegram 外部告警通道。
- `risk.yml` 的 `max_order_notional=1000` 高于 Phase 6.1 建议的初始小资金单笔上限 `250`。

## Phase 6.2 Live Activation Checklist

Phase 6.2 增加首次小资金实盘前的 activation checklist、严格 live risk 配置和 tax/trade export
验证。该步骤仍不启用实盘，不提交真实订单。

严格 live risk 配置：

- `strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml`
- `max_order_notional=250`
- `max_symbol_notional=500`
- `max_gross_notional=1000`
- `max_daily_loss=50`
- `max_drawdown_pct=0.05`

税务/成交导出验证：

```bash
./venv/bin/python -m packages.accounting.run_hummingbot_tax_export \
  --events-jsonl /Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_10_r2_hummingbot_events.jsonl \
  --account-id paper-main-hummingbot \
  --strategy-id crypto_relative_strength_v1 \
  --quote-asset USDT \
  --cad-fx-rate 1 \
  --fx-source validation_only_not_tax_filing \
  --output-csv reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export.csv \
  --summary-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export_summary.json \
  --summary-md reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export_summary.md
```

Activation checklist：

```bash
./venv/bin/python -m packages.reporting.run_live_activation_checklist \
  --live-readiness-json reports/live_readiness/crypto_relative_strength_v1_phase_6_1_live_readiness.json \
  --daily-report-json reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.json \
  --tax-export-summary-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export_summary.json \
  --live-risk-yml strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml \
  --session-id crypto_relative_strength_v1_phase_6_2_live_activation_checklist \
  --strategy-id crypto_relative_strength_v1 \
  --max-initial-live-order-notional 250 \
  --live-trading-enabled false \
  --global-kill-switch true \
  --output-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.json \
  --output-md reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.md
```

当前结果：`live_activation_ready`。

已通过：

- Phase 6.1 readiness 可用。
- Daily report 已生成。
- Trade tax export 已生成，`8` 行，对应 `8` 笔 filled orders。
- 严格 live risk 单笔上限已降到 `250`。
- `LIVE_TRADING_ENABLED=false`。
- `GLOBAL_KILL_SWITCH=true`。
- Telegram 外部告警通道已配置并通过测试消息验证。
- 凭据权限范围已由操作员确认。
- 交易所 allowlist / symbol / connector 范围已由操作员确认。
- 操作员 activation signoff 已确认。

阻断项：无。

税务导出当前使用 `validation_only_not_tax_filing` FX source，只能验证流水结构。正式报税前需要接入
官方或会计认可的 CAD 汇率，并做加拿大 ACB lot matching。

## Phase 6.3 Live Connector Preflight

Phase 6.3 增加真实 Hummingbot live connector 配置交接和预检。该步骤只检查配置文件是否存在、
字段名是否符合预期、前置 activation/signoff 是否仍然有效；报告只输出字段名，不输出 API key
或 secret 值。

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_live_connector_preflight \
  --activation-checklist-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.json \
  --credential-allowlist-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_credential_allowlist_review.json \
  --operator-signoff-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_operator_signoff.json \
  --live-risk-yml strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml \
  --hummingbot-root /Users/albertlz/Downloads/private_proj/hummingbot \
  --session-id crypto_relative_strength_v1_phase_6_3_live_connector_preflight \
  --strategy-id crypto_relative_strength_v1 \
  --expected-connector binance \
  --market-type spot \
  --allowed-pair BTC-USDT \
  --allowed-pair ETH-USDT \
  --output-json reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.json \
  --output-md reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.md
```

当前结果：`live_connector_preflight_ready`。

已通过：Phase 6.2 activation、凭据权限/allowlist、操作员 signoff、严格 live risk、
`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`、外部告警通道、交易所 key 未放入
`quant-system` 环境变量、Hummingbot `binance` connector 文件存在、必需 secret 字段名存在。

connector 文件：`/Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors/binance.yml`。
报告只记录 `binance_api_key`、`binance_api_secret` 字段名，不输出 API key 或 secret 值。

## 下一步

1. 继续保持 `LIVE_TRADING_ENABLED=false` 和 `GLOBAL_KILL_SWITCH=true`。
2. 不要扩大交易对或风险额度，首次 live 仍只允许 `BTC-USDT`、`ETH-USDT`。
3. 只有在最终 operator go 后，才进入真实 one-batch live runner 生成和启动。

## Phase 6.4 First Live Batch Activation Plan

Phase 6.4 把 Phase 6.3 ready 状态转成首次小资金 live batch 的执行计划。该步骤仍不提交真实
订单，不打开 live 开关，只生成批次范围、风控上限、激活顺序、回滚顺序和成交后导出流程。

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_live_batch_activation_plan \
  --live-connector-preflight-json reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.json \
  --credential-allowlist-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_credential_allowlist_review.json \
  --operator-signoff-json reports/live_readiness/crypto_relative_strength_v1_phase_6_2_operator_signoff.json \
  --live-risk-yml strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml \
  --session-id crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan_low_funds_50 \
  --strategy-id crypto_relative_strength_v1 \
  --batch-id crypto_relative_strength_v1_first_live_batch_001_low_funds_50 \
  --allowed-pair BTC-USDT \
  --allowed-pair ETH-USDT \
  --max-batch-orders 1 \
  --max-batch-notional 50 \
  --live-trading-enabled false \
  --global-kill-switch true \
  --output-json reports/live_readiness/crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan_low_funds_50.json \
  --output-md reports/live_readiness/crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan_low_funds_50.md
```

当前结果：`live_batch_activation_plan_approved`。

已通过：Phase 6.3 connector preflight、BTC/ETH allowlist、最多 `1` 笔订单、批次总名义
`50 USDT`、单笔 `50 USDT`、`LIVE_TRADING_ENABLED=false`、`GLOBAL_KILL_SWITCH=true`、
外部告警和密钥隔离。

最终 operator go 已确认，但本阶段仍未生成 live runner，`live_order_submission_armed=False`。

## Phase 6.5 Candidate Live Batch Package

Phase 6.5 刷新 BTC/ETH public market data，并基于最新已收盘 4h K 线生成候选 live batch。
该步骤只生成候选订单包，不生成可提交真实订单的 runner。

当前有效结果：低资金版 `live_batch_execution_package_ready_pending_exchange_state_check`。

候选订单：

- `BTC-USDT` market buy，估算名义 `50 USDT`
- 估算价格：`77371.32000000`
- 估算数量：`0.0006462342893981904405921987631`
- 信号时间：`2026-04-27T20:00:00+00:00`

操作员已确认低资金版 exchange state check：Binance spot 可用 USDT 足够覆盖 `50 USDT`
买入和手续费、当前没有异常 open orders、当前 BTC/ETH/USDT 持仓不会让本批次超过风险上限。

## Phase 6.6 Live One-Batch Runner

Phase 6.6 基于低资金版候选订单生成一次性 Hummingbot live runner，并安装到本机 Hummingbot
挂载目录。

当前结果：`live_one_batch_runner_ready`。

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.md`
- installed script: `/Users/albertlz/Downloads/private_proj/hummingbot/scripts/quant_system_live_one_batch.py`
- installed config: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/scripts/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`
- event log: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`
- batch cap: `1` order, `50 USDT` total, `50 USDT` per order
- runtime safety: `amount_safety_factor=0.99`、`quote_balance_safety_factor=1.02`、`max_price_deviation_pct=0.02`

该 runner 已在人工确认后启动并完成首次低资金 live batch；完成后一次性 runner 容器已停止。

## Phase 6.7 Live Post-Trade Reconciliation

Phase 6.7 对首次真实成交做 post-trade reconciliation、daily report 和 trade/tax export。

当前结果：`live_post_trade_reconciled_with_warnings`。

- reconciliation: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.md`
- daily report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/daily_report.md`
- trade/tax export: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/trade_tax_export.csv`
- submitted/filled/db fills: `1/1/1`
- gross quote notional: `49.266880 USDT`
- gross base quantity: `0.00064 BTC`
- fee: `0.00000064 BTC`
- net base quantity: `0.00063936 BTC`
- average fill price: `76979.5 USDT`
- balance deltas: `USDT -49.26688000`, `BTC +0.00063936`

WARN：Hummingbot 完成订单后 MQTT bridge 仍连接失败；tax export 使用
`validation_only_not_tax_filing` FX source，不能作为最终报税文件。

## Phase 6.8 Live Cooldown Review

Phase 6.8 对首次 live batch 进入冷却复盘。该步骤不启动 Hummingbot、不提交订单、不扩大交易对或额度。

当前结果：`live_cooldown_active_with_warnings`。

- cooldown review: `reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/cooldown_review.md`
- cooldown completed at: `2026-04-28T02:34:33.175500+00:00`
- minimum cooldown: `24` hours
- next review not before: `2026-04-29T02:34:33.175500+00:00`
- event log last event: `session_completed`
- event log lines: `3022`
- one-shot runner container: `not_found`
- installed runner config armed: `False`
- manual open orders check: `confirmed_clean`
- expansion allowed: `False`

冷却期内继续锁定：只允许复盘，不允许新增 live batch，不允许扩大到更多交易对，不允许提高 `50 USDT`
低资金 cap。

## Phase 6.9 Initial Closure and Position Lifecycle

Phase 6.9 对初始版本做闭环判定，并生成首次 BTC 小仓位的生命周期计划。该步骤不下单、不启动
Hummingbot、不扩大 live 权限。

当前结果：`initial_v0_flow_closed_with_warnings`。

- report: `reports/live_readiness/crypto_relative_strength_v1_phase_6_9_initial_closure_position_plan_low_funds_50/initial_closure_report.md`
- initial flow closed: `True`
- evidence complete: `True`
- next live decision: `NO_GO_COOLDOWN_ACTIVE`
- position stance: `HOLD_UNDER_OBSERVATION`
- strategy net BTC quantity: `0.00063936`
- entry cost basis quote: `49.266880 USDT`
- account ending BTC balance: `0.00074442`
- exit requires activation: `True`

剩余 P0：等待冷却窗口完成并重跑 Phase 6.8；继续禁止新增 live batch、扩大交易对或提高 `50 USDT`
cap。BTC 小仓位当前只观察，不自动退出；若要退出，需要单独生成并审批 one-shot sell plan。

详细路线见 `docs/roadmap.md`。
