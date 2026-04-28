# Phase 6.5 Candidate Live Batch Execution Package

- Generated at: `2026-04-28T02:12:41.545635+00:00`
- Decision: `live_batch_execution_package_ready_pending_exchange_state_check`
- Session id: `crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50`
- Strategy: `crypto_relative_strength_v1`
- Batch id: `crypto_relative_strength_v1_first_live_batch_001_low_funds_50`
- Connector: `binance`
- Allowed pairs: `BTC-USDT, ETH-USDT`
- Candidate orders: `1`
- Execution runner generated: `False`
- Live order submission armed: `False`

## Signal Summary

- signal_type: `relative_strength_rotation`
- lookback_window: `72`
- min_momentum: `0`
- top_n: `2`
- allowed_pairs: `['BTC-USDT', 'ETH-USDT']`
- ranked_pairs: `[{'trading_pair': 'BTC-USDT', 'momentum': '0.034237807009464912373334096', 'estimated_price': '77371.32000000', 'signal_timestamp': '2026-04-27T20:00:00+00:00'}]`
- selected_pairs: `['BTC-USDT']`
- latest_signal_timestamp: `2026-04-27T20:00:00+00:00`
- stale_or_insufficient_pairs: `[]`

## Candidate Orders

| Client Order Id | Pair | Side | Notional | Est Qty | Est Price | Momentum |
| --- | --- | --- | --- | --- | --- | --- |
| `crypto_relative_strength_v1_first_live_batch_001_low_funds_50-btc_usdt-1` | `BTC-USDT` | `buy` | `50` | `0.0006462342893981904405921987631` | `77371.32000000` | `0.034237807009464912373334096` |

## Risk Summary

- max_batch_orders: `1`
- max_batch_notional: `50`
- max_order_notional: `250`
- max_symbol_notional: `500`
- max_gross_notional: `1000`
- max_daily_loss: `50`
- max_drawdown_pct: `0.05`

## Checklist

- `PASS` Phase 6.4 activation plan approved: Phase 6.4 decision is live_batch_activation_plan_approved.
- `PASS` BTC/ETH market data refresh succeeded: refresh_statuses=['ok', 'ok'].
- `PASS` Candidate orders are inside allowlist: allowed_pairs=('BTC-USDT', 'ETH-USDT'); orders=['BTC-USDT'].
- `PASS` Candidate order count is inside batch cap: orders=1; cap=1.
- `PASS` Candidate order notionals are inside single-order cap: single_order_cap=250.
- `PASS` Candidate batch notional is inside batch cap: total_notional=50; cap=50.
- `PASS` BTC/ETH-only signal produced candidate orders: selected_pairs=['BTC-USDT'].
- `MANUAL_REQUIRED` Exchange balances and open orders reviewed: Verify Binance spot balances and no unexpected open orders before runner generation.

## Artifacts

- candidate_orders_jsonl: `reports/live_readiness/crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/candidate_orders.jsonl`
- package_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/package.json`
- package_md: `reports/live_readiness/crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/package.md`
