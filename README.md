# Quant System

一套面向加密市场的机构级量化交易系统。系统把 Hummingbot 定位为执行基础设施：
连接交易所、订阅行情、维护订单状态、处理精度和复用 Strategy V2 Executor。自研部分负责
alpha、组合、账户级风控、回测研究、实验追踪、监控和报表。

## 当前阶段

Phase 1: 工程骨架和安全边界。

- 不连接真实交易所。
- 不读取真实 API key。
- 不执行真实下单。
- 先定义核心数据模型、风险决策接口、执行路由接口和 Hummingbot 适配边界。

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

## 下一步

1. 用 `--refresh-market-data` 启动 24 小时 observation。
2. 复核 observation report 中的 refresh 状态、数据完整性、订单、权益和拒单。
3. 保持 live trading 禁用，直到 paper observation 连续稳定运行。

详细路线见 `docs/roadmap.md`。
