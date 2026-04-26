# Backtesting

Phase 3 的第一版目标是把 `crypto_momentum_v1` 跑成可复现的离线回测。

## Execution Assumptions

- 使用 SQLite 读取历史 K 线。
- 不调用 Hummingbot。
- 信号在 bar close 后生成。
- 调仓在下一根 bar open 执行。
- 持仓用下一根 bar close 计价。
- 当前 `spot` 模式不做裸空，`SHORT` 信号按空仓处理。
- 手续费使用固定百分比。
- 滑点使用固定 bps，买入价上调，卖出价下调。

## Run

```bash
./venv/bin/python -m packages.backtesting.run_backtest \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite \
  --output reports/backtests/crypto_momentum_v1_2025.json
```

输出指标包括：

- total return
- max drawdown
- turnover
- total fees
- trade count
- equity curve
- trade log

`reports/backtests/` 默认不进入 git。回测结果 JSON 会保存参数、数据覆盖和 git commit 短 hash，便于复现实验。

## Parameter Scan

Phase 3.1 支持批量扫描参数组合，并保存实验记录：

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

扫描器会跳过 `fast_window >= slow_window` 的组合。排名规则是：

1. total return 越高越好。
2. max drawdown 越低越好。
3. turnover 越低越好。

扫描 JSON 只保存每次运行的摘要指标，不保存完整 equity curve 和 trade log，避免实验文件过大。需要完整明细时，用选中的参数更新策略配置后单独运行 `run_backtest`。

## Train/Test Validation

Phase 3.2 支持把同一批参数组合分别跑训练集和测试集：

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

输出按训练集表现排名，同时包含测试集收益、测试集回撤和 train/test return gap。这个步骤用于判断 Phase 3.1 的最优参数是否只是在 2025 全样本上过拟合。

## Walk-Forward Validation

Phase 3.3 使用多折滚动验证。默认设置：

- 数据范围：`2023-01-01` 到 `2026-01-01`
- 训练窗口：6 个月
- 测试窗口：3 个月
- 步长：3 个月

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

每折先在训练集里按 Phase 3.1 的排序规则选参数，再记录该参数在下一段测试集的表现。JSON 会保留每折全部参数组合的 train/test 摘要，CSV 只保留每折被训练集选中的参数和测试表现。

## Regime Filter Scan

Phase 3.4 增加市场状态过滤：

- `min_trend_strength`: `abs(fast_ma / slow_ma - 1)` 的下限。
- `max_volatility`: rolling close-to-close volatility 的上限。
- `volatility_window`: 默认使用 `slow_window`。

策略配置里默认保留过滤器关闭状态，避免改变 baseline 行为：

```yaml
regime_filter:
  enabled: false
  min_trend_strength: "0"
  max_volatility: null
  volatility_window: null
```

真实验证命令：

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

Phase 3.4 结果没有改善 Phase 3.3 baseline：正收益折数仍为 `5/10`，平均测试收益从约
`3.92%` 降到约 `3.42%`，中位数仍为负。训练集选择从未选中 `max_volatility=0.04`，
说明这版波动率过滤没有带来有效 out-of-sample 改善。

## Relative Strength Rotation

Phase 3.5 增加 `relative_strength_rotation` 信号类型和 `crypto_relative_strength_v1` 策略。
它不再比较单个资产的快慢均线，而是在同一个 universe 内排序：

- `lookback_window`: 计算过去 N 根 K 线收益率。
- `top_n`: 选择排名靠前的资产，当前默认 `1`。
- `min_momentum`: 被选资产的最低动量门槛。

策略仍然是 spot only：如果没有资产达到 `min_momentum`，组合保持现金；不会做裸空。

全样本默认参数回测：

```bash
./venv/bin/python -m packages.backtesting.run_backtest \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --output reports/backtests/crypto_relative_strength_v1_2023_2025.json
```

默认参数结果较差：总收益约 `-8.51%`，最大回撤约 `28.22%`，换手约 `343x`，
交易次数 `690`，说明这个原始配置被交易成本和频繁切换拖累。

walk-forward 验证命令：

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

结果：

- 正收益测试折数：`6/10`
- 平均测试收益：约 `2.84%`
- 中位测试收益：约 `2.61%`
- 最好测试收益：约 `28.21%`
- 最差测试收益：约 `-13.59%`
- 最差测试回撤：约 `14.64%`

相对 Phase 3.3/3.4 的 MA baseline，它的正收益折数和中位数更好，但平均收益更低，
最差折的亏损和回撤更重。因此 Phase 3.5 的结论是：相对强弱轮动是更值得继续研究的
alpha 方向，但这版参数选择和风控还不足以进入 paper trading。

额外测试了更高 `min_momentum` 的网格：

```bash
./venv/bin/python -m packages.backtesting.run_walk_forward \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --experiment-id crypto_relative_strength_v1_phase_3_5_high_momentum \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --train-months 6 \
  --test-months 3 \
  --step-months 3 \
  --lookback-windows 24,48,72,108,144 \
  --min-momentum 0.05,0.10,0.15 \
  --fee-rates 0.0006 \
  --slippage-bps 2 \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_5_high_momentum_walk_forward.json \
  --summary-csv reports/backtests/crypto_relative_strength_v1_phase_3_5_high_momentum_walk_forward.csv
```

高门槛网格把最差测试收益改善到约 `-12.31%`，但正收益折数降到 `5/10`，
平均测试收益降到约 `1.28%`。单纯提高动量门槛不是足够好的解决方案。

## Risk-Adjusted Selection

Phase 3.6 增加 `SelectionPolicy`，用于控制参数扫描、train/test 和 walk-forward 的参数选择。
默认 `return_first` 保持旧行为：

1. total return 越高越好。
2. max drawdown 越低越好。
3. turnover 越低越好。
4. tail loss 越低越好。

新增 `risk_adjusted` 模式：

1. 先检查训练集约束：`min_return`、`max_drawdown`、`max_turnover`、`max_tail_loss`。
2. 满足约束的组合优先。
3. 在同一约束层内，按以下分数排序：

```text
score = total_return
        - drawdown_penalty * max_drawdown
        - turnover_penalty * turnover
        - tail_loss_penalty * tail_loss
```

`tail_loss` 是 equity curve 中最差单 bar 收益的绝对值，用于避免只看累计回撤而忽略
单次尾部冲击。

## Large-Cap Relative Strength

Phase 3.6 把 `crypto_relative_strength_v1` universe 扩为：

- BTC-USDT
- ETH-USDT
- BNB-USDT
- SOL-USDT
- XRP-USDT
- ADA-USDT

下载并导入 2023-2026 4h K 线：

```bash
./venv/bin/python -m packages.data.download_binance_candles \
  --symbols BTC-USDT ETH-USDT BNB-USDT SOL-USDT XRP-USDT ADA-USDT \
  --interval 4h \
  --start 2023-01-01 \
  --end 2026-01-01 \
  --output data/raw/binance_spot_largecap_4h_2023_2025.csv \
  --quality-report data/reports/binance_spot_largecap_4h_2023_2025_download_quality.json \
  --insecure-skip-tls-verify

./venv/bin/python -m packages.data.load_candles_sqlite \
  --input data/raw/binance_spot_largecap_4h_2023_2025.csv \
  --db data/warehouse/quant_system.sqlite \
  --quality-report data/reports/binance_spot_largecap_4h_2023_2025_sqlite_load_quality.json
```

导入后每个交易对都有 `6576/6576` 根 K 线，完整覆盖 `2023-01-01` 到 `2026-01-01`。

默认配置全样本回测：

```bash
./venv/bin/python -m packages.backtesting.run_backtest \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_6_largecap_default.json
```

结果：总收益约 `50.00%`，但最大回撤约 `40.76%`，换手约 `455.89x`，
交易次数 `1828`，说明默认配置收益高但风险和交易频率不可接受。

风险约束 walk-forward：

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

结果：

- 正收益测试折数：`7/10`
- 平均测试收益：约 `10.86%`
- 中位测试收益：约 `4.43%`
- 最好测试收益：约 `45.96%`
- 最差测试收益：约 `-15.85%`
- 最差测试回撤：约 `23.01%`
- 最差测试 tail loss：约 `4.96%`

同一网格下，旧 `return_first` 选择模式正收益折数为 `6/10`，中位测试收益约 `2.91%`，
最差测试收益约 `-23.02%`。风险约束选择降低了尾部亏损并提高了中位表现，但平均收益
低于收益优先版本。

更严格的风险约束版本正收益折数只有 `5/10`，中位测试收益约 `-2.10%`。这说明过度
约束训练集风险会错过有效行情，不能简单靠收紧阈值解决问题。

Phase 3.6 结论：多币种相对强弱 + 风险约束选择显著优于 Phase 3.5，但最差折仍有
约 `-15.85%` 测试亏损和约 `23.01%` 测试回撤，暂不进入 paper trading。

## Risk Overlay

Phase 3.7 在策略信号之后、订单生成之前增加组合级风险覆盖层。它不改变 alpha 排名，
只改变目标权重和本次交易量：

- `volatility_target`: 用目标组合权重和最近收益估算 realized portfolio volatility，
  当 realized volatility 高于目标时降低目标权重。
- `volatility_window`: realized volatility 的窗口。
- `min_risk_scale` / `max_risk_scale`: 风险缩放上下限。
- `max_drawdown_stop`: 全局高水位回撤熔断阈值。
- `drawdown_stop_cooldown_bars`: 熔断后强制 risk-off 的 bar 数。
- `reset_drawdown_high_watermark_on_stop`: 是否在熔断后重置高水位。Phase 3.7 使用
  `false`，即全局高水位熔断。
- `max_rebalance_turnover`: 单次调仓的总成交额上限，按当前权益百分比计。

当前 `crypto_relative_strength_v1` 的 Phase 3.7 组合配置：

```yaml
gross_target: "0.50"
max_symbol_weight: "0.25"
rebalance_threshold: "0.05"
volatility_target: "0.010"
volatility_window: 72
min_risk_scale: "0"
max_risk_scale: "1"
max_drawdown_stop: "0.10"
drawdown_stop_cooldown_bars: 36
reset_drawdown_high_watermark_on_stop: false
max_rebalance_turnover: "0.25"
```

默认配置全样本回测：

```bash
./venv/bin/python -m packages.backtesting.run_backtest \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_7_risk_overlay_default.json
```

结果：总收益约 `3.10%`，最大回撤约 `10.13%`，tail loss 约 `2.51%`，
换手约 `13.12x`，交易次数 `89`。这说明全局高水位熔断会很快把单次长期实验切到
risk-off，适合作为组合保护层，但不适合只用全样本收益评价 alpha。

Phase 3.7 walk-forward：

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

结果：

- 正收益测试折数：`7/10`
- 平均测试收益：约 `15.47%`
- 中位测试收益：约 `2.66%`
- 最好测试收益：约 `78.25%`
- 最差测试收益：约 `-4.79%`
- 最差测试回撤：约 `10.62%`
- 最差测试 tail loss：约 `5.19%`

与 Phase 3.6 相比，最差测试收益从约 `-15.85%` 改善到约 `-4.79%`，最差测试回撤从
约 `23.01%` 改善到约 `10.62%`。代价是中位测试收益从约 `4.43%` 降到约 `2.66%`，
说明风控覆盖层压住了尾部风险，也削弱了部分正常波动中的收益。

Phase 3.7 结论：风险覆盖层有效降低尾部亏损，当前候选比 Phase 3.6 更接近可运行研究
版本；但平均收益仍受少数强趋势折影响，paper trading 之前还需要容量、成交量参与率、
监控和 risk-off 恢复流程。

## Execution Constraints And Capacity

Phase 3.8 在执行层加入真实交易约束。约束顺序是：

1. 先由 alpha 生成目标权重。
2. 应用 Phase 3.7 的波动率目标和 risk-off。
3. 应用单次调仓换手上限。
4. 应用成交量参与率上限。
5. 低于最小下单额的订单跳过。

新增组合配置：

```yaml
risk_recovery_bars: 18
min_order_notional: "10"
max_participation_rate: "0.02"
```

新增输出指标：

- `recovery_bars`: risk-off 后处于恢复期的 bar 数。
- `min_order_skipped_count`: 因低于最小下单额而跳过的订单数。
- `min_order_skipped_notional`: 被最小下单额过滤的名义金额。
- `participation_capped_count`: 因成交量参与率上限而被截断的订单数。
- `participation_capped_notional`: 被参与率上限截掉的名义金额。
- `max_observed_participation_rate`: 实际成交里观察到的最大参与率。
- `estimated_participation_capacity_equity`: 在当前参与率上限下估算的资金容量。

Phase 3.8 默认全样本：

```bash
./venv/bin/python -m packages.backtesting.run_backtest \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_default.json
```

结果与 Phase 3.7 全样本一致：总收益约 `3.10%`，最大回撤约 `10.13%`，换手约
`13.12x`，交易次数 `89`。容量指标显示：

- 最小下单额跳过：`0`
- 参与率截断：`0`
- 最大观察参与率：约 `0.0405%`
- 估算容量：约 `49.37` 万 USDT

Phase 3.8 walk-forward：

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

结果与 Phase 3.7 相同，因为 1 万 USDT 资金规模没有触发容量约束：

- 正收益测试折数：`7/10`
- 平均测试收益：约 `15.47%`
- 中位测试收益：约 `2.66%`
- 最差测试收益：约 `-4.79%`
- 最差测试回撤：约 `10.62%`
- 最差测试 tail loss：约 `5.19%`
- 选中测试折最大观察参与率：约 `0.0865%`
- 选中测试折最小估算容量：约 `23.12` 万 USDT

容量压力测试：

```bash
./venv/bin/python -m packages.backtesting.run_backtest \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --initial-equity 1000000 \
  --output reports/backtests/crypto_relative_strength_v1_phase_3_8_capacity_stress_1m.json
```

100 万 USDT 压力测试触发了参与率上限：`participation_capped_count=14`，
被截断名义金额约 `66.84` 万 USDT，最大观察参与率被限制在 `2%`。这说明当前执行约束
对小资金无影响，但能在资金规模放大后限制不可成交的交易。

Phase 3.8 结论：当前候选在 1 万 USDT 研究资金下没有容量瓶颈，估算容量下限约
`23.12` 万 USDT；但如果资金上升到 100 万 USDT，参与率约束会开始实质影响成交。
进入 paper trading 前，需要把这些指标接入运行时监控和日报。

## Paper Readiness

Phase 3.9 增加 paper trading 启动前检查。输入是 Phase 3.8 的 walk-forward JSON 和
容量压力测试 JSON，输出三类文件：

- readiness JSON：机器可读的状态、阈值、告警和建议动作。
- readiness Markdown：人工检查用日报。
- risk-off runbook：触发熔断或 kill switch 后的恢复流程。

```bash
./venv/bin/python -m packages.reporting.run_paper_readiness_report \
  --walk-forward-json reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_walk_forward.json \
  --capacity-stress-json reports/backtests/crypto_relative_strength_v1_phase_3_8_capacity_stress_1m.json \
  --output-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --output-md reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_daily_report.md \
  --runbook-md reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_risk_off_runbook.md
```

默认阈值：

- 正收益折数比例至少 `70%`。
- 中位测试收益不低于 `0`。
- 最差测试亏损不超过 `5%`。
- 最差测试回撤不超过 `12%`。
- 最差测试 tail loss 不超过 `6%`。
- 选中测试折最小估算容量不低于 `100000` USDT。

当前输出状态是 `paper_ready_with_warnings`，没有 CRITICAL 阻断。WARN 项：

- `Return concentration`: 平均收益受最好测试折影响较大。
- `Risk-off observed`: 选中测试折中出现 risk-off，需要恢复手册。
- `Capacity stress capped orders`: 100 万 USDT 压力测试触发参与率上限。

Phase 3.9 结论：当前候选可以进入小资金 paper trading 准备，但必须带 readiness
检查、显式 kill switch、risk-off 恢复手册和每日人工复核；live trading 继续禁止。
