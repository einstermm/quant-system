# Deployment

当前提供本地基础设施和单容器 Web 部署入口。

## Web Container

构建并启动 Web API + 静态前端：

```bash
docker compose up --build web
```

访问入口：

- API 信息页：`http://127.0.0.1:8000/`
- 前端页面：`http://127.0.0.1:8000/app`
- 部署状态：`http://127.0.0.1:8000/api/deployment/status`

运行目录挂载：

- `./data:/app/data`
- `./reports:/app/reports`
- `./logs:/app/logs`
- `./strategies:/app/strategies:ro`

部署时建议设置写操作 API key：

```bash
export QUANT_WEB_API_KEY='<replace-with-strong-key>'
docker compose up --build web
```

容器只暴露 Web API 和静态前端，不启动 Hummingbot，也不提交真实订单。

## Local Infrastructure

本地数据库/缓存：

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

## Observation Review Gate

Phase 4.3 在进入 Hummingbot Sandbox 前运行：

```bash
./venv/bin/python -m packages.reporting.run_paper_observation_review \
  --observation-jsonl reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_observation.jsonl \
  --ledger-jsonl reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_ledger.jsonl \
  --readiness-json reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json \
  --initial-equity 2000 \
  --output-json reports/paper_trading/crypto_relative_strength_v1_phase_4_3_observation_review.json \
  --output-md reports/paper_trading/crypto_relative_strength_v1_phase_4_3_observation_review.md
```

允许进入 Phase 5 Sandbox 准备的决策：

- `sandbox_ready`
- `sandbox_ready_with_warnings`，但 WARN 必须写入 Phase 5 runbook

禁止进入 Phase 5 的决策：

- `blocked`

当前 Phase 4.3 决策为 `sandbox_ready_with_warnings`。它只允许准备 Hummingbot Sandbox，
不允许配置真实交易所密钥或开启 live trading。

## Hummingbot Sandbox Preparation

Phase 5 准备阶段从 Phase 4.3 review 和 paper ledger 生成 sandbox manifest：

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

允许进入 Hummingbot sandbox/paper mode 对接的准备决策：

- `sandbox_prepared`
- `sandbox_prepared_with_warnings`，但 WARN 必须进入 sandbox runbook

禁止启动 Hummingbot sandbox/paper mode 的准备决策：

- `blocked`

当前准备决策为 `sandbox_prepared_with_warnings`。manifest 的
`live_trading_enabled=false` 必须保持不变，且只能加载到 Hummingbot sandbox 或 paper mode。
真实交易所密钥、live connector 和 live order submission 继续禁止。

## Sandbox Event Reconciliation

Phase 5.1 对 Hummingbot sandbox/paper mode 事件做标准化和对账。没有外部 Hummingbot
runtime 时，可以先用 manifest replay 验证本系统的对账逻辑：

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

真实 Hummingbot sandbox/paper event export 对账：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_reconciliation \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --events-jsonl reports/hummingbot_sandbox/<hummingbot_events>.jsonl \
  --starting-quote-balance 2000 \
  --quote-asset USDT \
  --output-json reports/hummingbot_sandbox/<session>_reconciliation.json \
  --output-md reports/hummingbot_sandbox/<session>_reconciliation.md
```

对账阻断项包括：未知订单 ID、缺失提交事件、缺失终态事件、订单失败/取消、断连、
订单异常、余额异常、成交数量不一致、余额缺失或余额不一致。价格和手续费偏离先作为
WARN 处理，因为真实 sandbox fill 可能与 manifest 的估算价格不同。

## Sandbox Session Gate

Phase 5.2 在启动或延长真实 Hummingbot sandbox/paper session 前运行：

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

真实 Hummingbot event export 存在后，把 `--event-source replay` 改为
`--event-source hummingbot_export`，并把 `--event-jsonl` 指向真实导出的 JSONL。

Phase 5.2 阻断项包括：

- manifest 或环境开启 live trading。
- 当前 shell 中检测到常见交易所 API key 环境变量。
- Phase 5 准备或 Phase 5.1 对账结果为 `blocked`。
- 没有显式 `--allow-warnings` 却存在上游 warning。
- 真实 export 模式下 event JSONL 不存在。
- 订单提交数、终态数、未知订单、余额对账不满足要求。

当前 replay gate 决策为 `sandbox_session_ready_with_warnings`。这只允许准备真实
Hummingbot sandbox/paper session，不允许 live trading。

## Sandbox Handoff Package

Phase 5.3 生成交给外部 Hummingbot sandbox/paper dry run 的文件包：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_package \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --session-gate-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_2_sandbox_session_gate.json \
  --output-dir reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_3_session_package \
  --allow-warnings
```

包内文件：

- `controller_configs.json` 和 `controller_configs/*.json`: 按交易对拆分的 sandbox controller 输入。
- `orders.jsonl`: 每笔 sandbox order config。
- `expected_event_schema.json`: Hummingbot event JSONL 字段要求。
- `event_capture_template.jsonl`: 事件采集模板。
- `operator_runbook.md`: 外部 sandbox session 操作清单。
- `package_summary.json` / `package_summary.md`: 包生成结果和 warning。

当前 package 决策为 `sandbox_package_ready_with_warnings`。它仍基于 replay gate，因此只能用于
第一次外部 dry run；真实 Hummingbot event export 产生后，必须重新运行 Phase 5.1、Phase 5.2
和 Phase 5.3。

## Sandbox Export Acceptance

Phase 5.4 用一个命令验收 Hummingbot sandbox/paper event export，并自动重跑
reconciliation、session gate 和 handoff package：

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

真实 Hummingbot export 使用方式：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_export_acceptance \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --prepare-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_prepare.json \
  --events-jsonl reports/hummingbot_sandbox/<real_hummingbot_events>.jsonl \
  --output-dir reports/hummingbot_sandbox/<session>_export_acceptance \
  --session-id <session> \
  --event-source hummingbot_export \
  --starting-quote-balance 2000 \
  --quote-asset USDT \
  --allow-warnings
```

如果事件来自 Hummingbot CLI paper connector 的默认账户，通常不要传
`--starting-quote-balance 2000`，因为 Hummingbot paper 账户初始资产不是 Phase 4 本地账户。
这时 acceptance 会保留 balance events，但把余额数量核对标记为 skipped WARN。

当前 replay acceptance 决策为 `sandbox_export_accepted_with_warnings`。Phase 5.7 真实
Hummingbot CLI paper export acceptance 也已通过，决策为
`sandbox_export_accepted_with_warnings`。任何 live trading 仍然禁止。

## Hummingbot Runtime Preflight

Phase 5.5 在启动本机 Hummingbot / Hummingbot API 前扫描挂载目录，确认不会加载 live connector
或真实交易所密钥字段：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_runtime_preflight \
  --scan-root /Users/albertlz/Downloads/private_proj/hummingbot-api/bots \
  --scan-root /Users/albertlz/Downloads/private_proj/hummingbot/conf \
  --session-id crypto_relative_strength_v1_phase_5_5_local_runtime_preflight \
  --expected-connector binance_paper_trade \
  --output-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_5_runtime_preflight.json \
  --output-md reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_5_runtime_preflight.md
```

初始本机结果为 `blocked`：

- Docker 中存在 `hummingbot`、`hummingbot-api`、`hummingbot-broker`、`hummingbot-postgres` 容器，
  但当前均未运行。
- `hummingbot-api` 曾加载 `master_account/binance_perpetual`，历史日志显示它请求过 Binance
  Futures 账户接口。
- 预检在 `hummingbot-api/bots/credentials/master_account/connectors/binance_perpetual.yml`
  发现 live connector 和 API key/secret 字段；报告只记录字段名，密钥值不会输出。
- 未发现 `binance_paper_trade` paper connector。

已执行的修复：

- live connector 文件已移出 `credentials/master_account/connectors` 自动扫描目录，并归档到
  `hummingbot-api/bots/archived/phase_5_5_disabled_live_connector_20260427T030953Z/`。
- 隔离后重新运行 Phase 5.5，结果为 `runtime_ready`。
- 当前 `hummingbot-api`、`hummingbot-broker` 和 `hummingbot-postgres` 已启动，本地
  `GET /` 返回 `{"status":"running"}`。

当前限制：

- `hummingbot-api` 的 `/connectors` registry 不包含 `binance_paper_trade`。
- 不要通过 API trading connector 路由提交 Phase 5 paper 订单。
- 第一次真实 Hummingbot dry run 应走 Hummingbot CLI paper mode，或先单独补齐 API 对 paper
  connector 初始化的支持。

只有真实 Hummingbot paper/sandbox event JSONL 通过 Phase 5.4 export acceptance 后，才允许延长
sandbox session。live trading 继续禁止。

## Hummingbot CLI Paper Handoff

Phase 5.6 生成可安装到 Hummingbot CLI paper mode 的 Strategy V2 文件：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_cli_paper_handoff \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --runtime-preflight-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_5_runtime_preflight_after_isolation.json \
  --output-dir reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_6_cli_paper_handoff \
  --session-id crypto_relative_strength_v1_phase_5_6_cli_paper \
  --hummingbot-root /Users/albertlz/Downloads/private_proj/hummingbot \
  --allow-warnings
```

当前结果为 `cli_paper_handoff_ready`。已安装到 Hummingbot CLI 挂载目录：

- `controllers/generic/quant_system_sandbox_order_controller.py`
- `conf/controllers/crypto_relative_strength_v1_phase_5_6_ada_usdt.yml`
- `conf/controllers/crypto_relative_strength_v1_phase_5_6_btc_usdt.yml`
- `conf/controllers/crypto_relative_strength_v1_phase_5_6_xrp_usdt.yml`
- `conf/scripts/crypto_relative_strength_v1_phase_5_6_v2_with_controllers.yml`

容器内非交易校验：

```bash
docker compose run --rm hummingbot /bin/bash -lc \
  'conda activate hummingbot && python -m py_compile /home/hummingbot/controllers/generic/quant_system_sandbox_order_controller.py'
```

Hummingbot CLI paper dry run 启动命令：

```bash
cd /Users/albertlz/Downloads/private_proj/hummingbot
docker compose run --rm \
  -e CONFIG_FILE_NAME=v2_with_controllers.py \
  -e SCRIPT_CONFIG=crypto_relative_strength_v1_phase_5_6_v2_with_controllers.yml \
  hummingbot
```

启动后输入 Hummingbot 密码。该 session 使用 `binance_paper_trade`，不要连接或配置 live exchange
connector。运行前如需清空旧事件文件，删除：

```bash
/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_6_hummingbot_events.jsonl
```

运行结束后，用该 JSONL 进入 Phase 5.4 export acceptance。若 Hummingbot 没有写出 balance event，
第一次验收可以追加 `--no-require-balance-event`，但订单 submitted/filled 必须完整。

Phase 5.6 runtime 发现：controller 文件能通过语法和 YAML 校验，但当前 Hummingbot paper connector
与 Strategy V2 `OrderExecutor` 路径存在 `_order_tracker` 兼容性问题。因此当前真实 paper dry run
使用 Phase 5.7 direct paper handoff。

## Hummingbot CLI Direct Paper Handoff

Phase 5.7 生成直接提交 Hummingbot paper buy/sell 的脚本，绕开 controller `OrderExecutor`
兼容性问题：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_cli_direct_paper_handoff \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --runtime-preflight-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_5_runtime_preflight_after_isolation.json \
  --output-dir reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_7_direct_paper_handoff \
  --session-id crypto_relative_strength_v1_phase_5_7_direct_paper \
  --hummingbot-root /Users/albertlz/Downloads/private_proj/hummingbot \
  --allow-warnings
```

已安装到 Hummingbot CLI 挂载目录：

- `scripts/quant_system_cli_paper_orders.py`
- `conf/scripts/crypto_relative_strength_v1_phase_5_7_direct_paper.yml`

headless 启动命令：

```bash
cd /Users/albertlz/Downloads/private_proj/hummingbot
docker compose run -d \
  --name quant-phase-5-7-direct-paper \
  -e CONFIG_PASSWORD=admin \
  -e HEADLESS_MODE=true \
  -e SCRIPT_CONFIG=crypto_relative_strength_v1_phase_5_7_direct_paper.yml \
  hummingbot
```

事件文件：

```bash
/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_7_hummingbot_events.jsonl
```

真实 export acceptance 命令：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_export_acceptance \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_manifest.json \
  --prepare-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_sandbox_prepare.json \
  --events-jsonl /Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_7_hummingbot_events.jsonl \
  --output-dir reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_7_export_acceptance \
  --session-id crypto_relative_strength_v1_phase_5_7_direct_paper \
  --event-source hummingbot_export \
  --quote-asset USDT \
  --allow-warnings \
  --amount-tolerance 0.0001
```

当前 Phase 5.7 结果为 `sandbox_export_accepted_with_warnings`：真实 Hummingbot paper export
包含 submitted `8`、filled `8`、balance `10`，无 failed/canceled/unknown/missing order。
WARN 来自 1 笔 XRP paper 卖单按可用余额裁剪、实时 fill 价格偏移、手续费偏移和余额数量核对跳过。
live trading 继续禁止。

## Hummingbot Observation Window Gate

Phase 5.8 在启动更长 Hummingbot CLI direct paper observation window 前运行。它读取 Phase 5.4
真实 acceptance 和 Hummingbot event JSONL，确认订单生命周期干净，并把可接受 WARN 写入下一轮
runbook。

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

当前 Phase 5.8 结果为 `hummingbot_observation_window_ready_with_warnings`：

- event source: `hummingbot_export`
- window duration: `0.0111` hours，低于目标 `2` hours
- submitted/filled/terminal: `8/8/8`
- failed/canceled/unknown/missing orders: `0`
- carry-forward WARN: XRP paper 卖单余额裁剪、fill price drift、fee drift、balance reconciliation skipped

Phase 5.8 只允许准备更长 sandbox observation window，不表示长窗口已经完成。下一轮必须先从最新
批准的 paper ledger 重新生成 manifest，再生成并安装 Phase 5.7 direct handoff；不要直接重复提交
旧 manifest。live trading 继续禁止。

## Hummingbot Direct Paper Observation Smoke

Phase 5.9 让 direct paper script 支持 observation window：最短运行时长、heartbeat、周期余额快照、
final balance snapshot 和 `session_completed` 事件。

重新生成 manifest：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_sandbox_prepare \
  --review-json reports/paper_trading/crypto_relative_strength_v1_phase_4_3_observation_review.json \
  --ledger-jsonl reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_ledger.jsonl \
  --allow-warnings \
  --connector-name binance_paper_trade \
  --controller-name quant_system_sandbox_order_controller \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_9_sandbox_manifest.json \
  --report-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_9_sandbox_prepare.json \
  --report-md reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_9_sandbox_prepare.md
```

生成 120 秒 smoke handoff：

```bash
./venv/bin/python -m packages.adapters.hummingbot.run_cli_direct_paper_handoff \
  --manifest-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_9_sandbox_manifest.json \
  --runtime-preflight-json reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_5_runtime_preflight_after_isolation.json \
  --output-dir reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_9_direct_paper_observation_handoff \
  --session-id crypto_relative_strength_v1_phase_5_9_direct_paper_observation \
  --hummingbot-root /Users/albertlz/Downloads/private_proj/hummingbot \
  --allow-warnings \
  --event-log-path /home/hummingbot/data/crypto_relative_strength_v1_phase_5_9_hummingbot_events.jsonl \
  --script-config-name crypto_relative_strength_v1_phase_5_9_direct_paper_observation.yml \
  --observation-min-runtime-seconds 120 \
  --heartbeat-interval-seconds 15 \
  --balance-snapshot-interval-seconds 30
```

已安装到 Hummingbot CLI 挂载目录：

- `scripts/quant_system_cli_paper_orders.py`
- `conf/scripts/crypto_relative_strength_v1_phase_5_9_direct_paper_observation.yml`

当前 Phase 5.9 smoke 结果：

- event JSONL: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_9_hummingbot_events.jsonl`
- acceptance: `sandbox_export_accepted_with_warnings`
- observation review: `hummingbot_observation_window_ready_with_warnings`
- events: `85`
- submitted/filled: `8/8`
- heartbeat/balance/session_completed: `9/58/1`
- failed/canceled/unknown/missing orders: `0`

Hummingbot headless 在写出 `session_completed` 后容器进程可能仍保持运行；确认事件完整后可以手动
`docker stop <container>` 收尾。下一轮目标可以把 `--observation-min-runtime-seconds` 调整为
`7200` 做 2 小时 direct paper observation。live trading 继续禁止。
