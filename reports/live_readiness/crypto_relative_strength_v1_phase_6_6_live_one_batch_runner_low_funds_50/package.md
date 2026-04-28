# Phase 6.6 Live One-Batch Runner

- Generated at: `2026-04-28T02:20:38.200263+00:00`
- Decision: `live_one_batch_runner_ready`
- Session id: `crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50`
- Script config: `crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`
- Event log path: `/home/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`
- Orders: `1`
- Connector: `binance`
- Live order submission armed: `True`

## Summary

- candidate_package_decision: `live_batch_execution_package_ready_pending_exchange_state_check`
- strategy_id: `crypto_relative_strength_v1`
- batch_id: `crypto_relative_strength_v1_first_live_batch_001_low_funds_50`
- connector_name: `binance`
- order_count: `1`
- total_requested_quote_notional: `50`
- max_batch_notional: `50`
- max_order_notional: `50`
- allowed_pairs: `['BTC-USDT', 'ETH-USDT']`
- live_order_submission_armed: `True`
- exchange_state_confirmed: `True`
- amount_safety_factor: `0.99`
- quote_balance_safety_factor: `1.02`
- max_price_deviation_pct: `0.02`

## Checklist

- `PASS` Phase 6.5 candidate package ready: Phase 6.5 decision is live_batch_execution_package_ready_pending_exchange_state_check.
- `PASS` Exchange state manually confirmed: Operator confirmed Binance spot balance, open orders, and exposure constraints.
- `PASS` One live order only: orders=1.
- `PASS` All orders are inside allowlist: allowed_pairs=['BTC-USDT', 'ETH-USDT'].
- `PASS` All orders are inside order cap: max_order_notional=50.
- `PASS` Batch is inside notional cap: total_notional=50; max_batch_notional=50.
- `PASS` Event log path is clear: Existing event logs must be archived before a live run. Evidence: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`

## Install Targets

- script_source: `/Users/albertlz/Downloads/private_proj/hummingbot/scripts/quant_system_live_one_batch.py`
- script_config: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/scripts/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`
- event_log_host_path: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`

## Launch Command

Do not run this unless you intend to place the live order.

```bash
if docker ps --format '{{.Names}}' | grep -qx hummingbot; then echo 'Stop the existing hummingbot container first: docker stop hummingbot'; exit 1; fi; read -rsp 'Hummingbot password: ' HBOT_PASSWORD; echo; docker run --rm --name quant-phase-6-6-live-one-batch-low-funds-50 -v /Users/albertlz/Downloads/private_proj/hummingbot/conf:/home/hummingbot/conf -v /Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors:/home/hummingbot/conf/connectors -v /Users/albertlz/Downloads/private_proj/hummingbot/conf/scripts:/home/hummingbot/conf/scripts -v /Users/albertlz/Downloads/private_proj/hummingbot/data:/home/hummingbot/data -v /Users/albertlz/Downloads/private_proj/hummingbot/logs:/home/hummingbot/logs -v /Users/albertlz/Downloads/private_proj/hummingbot/scripts:/home/hummingbot/scripts hummingbot/hummingbot:latest /bin/bash -lc "conda activate hummingbot && ./bin/hummingbot_quickstart.py --headless --config-password \"$HBOT_PASSWORD\" --v2 crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml"
```

## Artifacts

- script_source: `reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/scripts/quant_system_live_one_batch.py`
- script_config: `reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/conf/scripts/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`
- event_log_host_path: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`
- package_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.json`
- package_md: `reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.md`
