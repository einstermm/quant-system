# Hummingbot Daily Report

- Generated at: `2026-04-27T17:37:55.121310+00:00`
- Status: `daily_report_ready_with_warnings`
- Session id: `crypto_relative_strength_v1_phase_6_1_daily_report`
- Strategy: `crypto_relative_strength_v1`

## Event Window

- Started at: `2026-04-27T15:18:19.001884+00:00`
- Completed at: `2026-04-27T17:18:19.013944+00:00`
- Duration hours: `2.00000335`
- Event counts: `{'session_started': 1, 'heartbeat': 121, 'balance': 258, 'submitted': 8, 'filled': 8, 'session_completed': 1}`

## Trading

- Submitted orders: `8`
- Filled orders: `8`
- Buy orders: `6`
- Sell orders: `2`
- Gross notional quote: `1959.705403998000008573058651`
- Buy notional quote: `1472.725630567030000474493660`
- Sell notional quote: `486.9797734309700080985649914`
- Total fee quote: `1.959705403998000008573058651`
- Net quote trade flow after fees: `-987.7055625400579923845017273`

## Balances

- Balance assets: `['ADA', 'BTC', 'DOGE', 'ETH', 'HBOT', 'SOL', 'USDC', 'USDT', 'WETH', 'XRP']`
- Quote asset: `USDT`
- Quote balance delta: `-986.23283690949096238402723`
- Balance deltas: `{'ADA': '0.0000000000', 'BTC': '0.0064331604', 'DOGE': '0', 'ETH': '0', 'HBOT': '0', 'SOL': '0', 'USDC': '0', 'USDT': '-986.23283690949096238402723', 'WETH': '0', 'XRP': '0.0000000000'}`

## Carried Warnings

- `WARN` Acceptance has warnings: Acceptance decision is sandbox_export_accepted_with_warnings.
- `WARN` Reconciliation has warnings: Reconciliation decision is sandbox_reconciled_with_warnings.
- `WARN` Submitted amount adjusted: Carry forward Hummingbot paper amount adjustment warnings.
- `WARN` Fill price drift: Carry forward fill price drift warnings into the next runbook.
- `WARN` Fee drift: Carry forward Hummingbot paper fee drift warnings into the next runbook.
- `WARN` Balance reconciliation skipped: Hummingbot paper account balances were exported but not quantity-reconciled.

## Alerts

- `WARN` Observation warnings carried: Observation review warnings are carried into this daily report.

## Artifacts

- events_jsonl: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_10_r2_hummingbot_events.jsonl`
- observation_review_json: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.json`
