# Deployment

当前只提供本地基础设施：

```bash
docker compose up -d postgres redis
```

本阶段不启动 Hummingbot，不配置真实交易所密钥。后续接入顺序：

1. 本地 Hummingbot paper mode。
2. Hummingbot API。
3. 本系统 trader gateway 调用 Hummingbot API。
4. Grafana/Prometheus 指标。
5. 告警渠道。

## Paper Readiness Gate

进入任何 paper session 前先运行：

```bash
./venv/bin/python -m packages.reporting.run_paper_readiness_report \
  --walk-forward-json reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_walk_forward.json \
  --capacity-stress-json reports/backtests/crypto_relative_strength_v1_phase_3_8_capacity_stress_1m.json \
  --output-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --output-md reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_daily_report.md \
  --runbook-md reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_risk_off_runbook.md
```

允许进入 paper 准备的状态：

- `paper_ready`
- `paper_ready_with_warnings`，但 WARN 必须人工确认

禁止进入 paper 的状态：

- `blocked`

无论 readiness 状态如何，`LIVE_TRADING_ENABLED` 都必须保持关闭。

## Local Paper Cycle

Phase 4 当前只支持本地单次 paper cycle：

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

运行规则：

- readiness 状态为 `paper_ready_with_warnings` 时，必须显式传入
  `--allow-readiness-warnings`。
- ledger 使用 JSONL 追加写入，用于重建 paper cash、position 和 equity。
- runner 只使用 `PaperExecutionClient` 记录模拟成交，不调用 Hummingbot。
- 真实交易所密钥和 `LIVE_TRADING_ENABLED=true` 仍然禁止。

可选 kill switch 文件：

```json
{"active": true, "reason": "manual stop"}
```

传入 `--kill-switch-file <path>` 后，runner 会在启动时读取开关状态，并把该状态用于
本次 cycle 的每个订单意图。当 `active=true` 时，新订单被拒绝，ledger 不新增成交。

## Paper Observation Loop

Phase 4.1 使用 observation loop 连续运行本地 paper cycle，并输出三类文件：

- paper order ledger: 模拟成交 JSONL。
- observation log: 每轮 cycle 的状态、权益、订单、目标权重和数据质量 JSONL。
- summary/report: 当前观察摘要 JSON 和 Markdown。

smoke run：

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

24 小时观察：

```bash
./venv/bin/python -m packages.paper_trading.run_paper_observation \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --readiness-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --allow-readiness-warnings \
  --ledger reports/paper_trading/crypto_relative_strength_v1_phase_4_1_24h_ledger.jsonl \
  --observation-log reports/paper_trading/crypto_relative_strength_v1_phase_4_1_24h_observation.jsonl \
  --summary-json reports/paper_trading/crypto_relative_strength_v1_phase_4_1_24h_summary.json \
  --report-md reports/paper_trading/crypto_relative_strength_v1_phase_4_1_24h_report.md \
  --account-id paper-main \
  --initial-equity 2000 \
  --duration-hours 24 \
  --interval-seconds 60
```

## Market Data Refresh

Phase 4.2 支持在每轮 observation 前刷新 Binance spot public K 线：

```bash
./venv/bin/python -m packages.paper_trading.run_paper_observation \
  --strategy-dir strategies/crypto_relative_strength_v1 \
  --db data/warehouse/quant_system.sqlite \
  --readiness-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --allow-readiness-warnings \
  --ledger reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_ledger.jsonl \
  --observation-log reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_observation.jsonl \
  --summary-json reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_summary.json \
  --report-md reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_report.md \
  --account-id paper-main \
  --initial-equity 2000 \
  --refresh-market-data \
  --duration-hours 24 \
  --interval-seconds 60
```

刷新规则：

- 默认使用 Binance public API，不需要交易所密钥。
- 默认 `--refresh-close-delay-seconds 60`，避免读取刚形成但可能未稳定的当前 K 线。
- 默认 `--refresh-overlap-bars 2`，每轮重取尾部 K 线并 upsert 到 SQLite。
- 如果某个交易对刷新失败，本轮 cycle 会失败并写入 observation log，不会继续下单。
- 每轮 observation 的 `pre_cycle.market_data_refresh` 会记录每个交易对的刷新状态。
- 如果本地网络使用自签证书代理，可临时追加 `--insecure-skip-tls-verify` 验证 public
  data 链路；该参数只应用于公开行情请求，不得用于交易接口。

该阶段仍是 paper execution：不调用 Hummingbot，不提交真实订单。
