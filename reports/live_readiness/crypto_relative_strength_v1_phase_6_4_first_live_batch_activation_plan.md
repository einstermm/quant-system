# Phase 6.4 First Live Batch Activation Plan

- Generated at: `2026-04-28T02:09:30.945820+00:00`
- Decision: `live_batch_activation_plan_approved`
- Session id: `crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan`
- Strategy: `crypto_relative_strength_v1`
- Batch id: `crypto_relative_strength_v1_first_live_batch_001`
- Connector: `binance`
- Market type: `spot`
- Allowed pairs: `BTC-USDT, ETH-USDT`

## Batch Scope

- batch_id: `crypto_relative_strength_v1_first_live_batch_001`
- mode: `single_supervised_live_batch`
- connector: `binance`
- market_type: `spot`
- allowed_pairs: `['BTC-USDT', 'ETH-USDT']`
- max_orders: `2`
- max_total_notional: `500`
- live_order_submission_armed: `False`
- requires_final_operator_go: `True`

## Risk Controls

- max_batch_orders: `2`
- max_batch_notional: `500`
- max_order_notional: `250`
- max_symbol_notional: `500`
- max_gross_notional: `1000`
- max_daily_loss: `50`
- max_drawdown_pct: `0.05`
- one_batch_only: `True`
- auto_expand_pairs: `False`
- auto_expand_limits: `False`
- spot_only_no_margin: `True`
- sell_only_existing_spot_balance: `True`

## Environment

- live_trading_enabled: `False`
- global_kill_switch: `True`
- exchange_key_env_detected: `False`
- alert_channel_configured: `True`

## Checklist

- `PASS` Phase 6.3 live connector preflight ready: Phase 6.3 decision is live_connector_preflight_ready. Evidence: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors/binance.yml`
- `PASS` First live allowlist remains exact: preflight=('BTC-USDT', 'ETH-USDT'); credential=('BTC-USDT', 'ETH-USDT'); operator=('BTC-USDT', 'ETH-USDT').
- `PASS` Batch order count is capped: max_batch_orders=2; allowed_pairs=2.
- `PASS` Batch notional is inside gross risk limit: max_batch_notional=500; max_gross_notional=1000.
- `PASS` Single order cap remains approved: max_order_notional=250; approved=250.
- `PASS` Live trading remains disabled before final go: LIVE_TRADING_ENABLED must stay false while this is only a plan.
- `PASS` Global kill switch remains enabled before final go: GLOBAL_KILL_SWITCH must stay true until the explicit activation step.
- `PASS` External alert channel remains configured: External alerts are required for any live batch.
- `PASS` Exchange keys are not stored in quant-system env: Real exchange credentials must stay in Hummingbot connector config.
- `PASS` Final operator go/no-go: Final operator go has been recorded.

## Activation Sequence

1. Rerun Phase 6.3 immediately before the live batch.
2. Send and verify one external alert test.
3. Confirm Binance spot account balances and no unexpected open orders.
4. Generate the final live batch from the latest BTC/ETH-only signal.
5. Cap the batch to two orders and 500 USDT total notional.
6. Only after final operator go, arm the one-batch live runner.
7. Submit one supervised batch only, then immediately disarm live trading.

## Rollback Sequence

1. Stop the Hummingbot container or script immediately.
2. Set GLOBAL_KILL_SWITCH=true and LIVE_TRADING_ENABLED=false.
3. Cancel any open orders in Hummingbot and confirm in the Binance spot UI.
4. Do not restart live trading before reconciliation is complete.

## Post Batch Sequence

1. Export Hummingbot events and exchange fills.
2. Run daily report, reconciliation, and tax/trade export.
3. Compare Hummingbot fills against Binance fills and balances.
4. Document PnL, fees, slippage, alerts, and any manual intervention.

## Artifacts

- live_connector_preflight_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.json`
- credential_allowlist_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_credential_allowlist_review.json`
- operator_signoff_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_operator_signoff.json`
- live_risk_yml: `strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml`
