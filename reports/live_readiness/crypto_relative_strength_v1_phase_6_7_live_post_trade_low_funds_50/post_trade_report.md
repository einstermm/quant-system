# Phase 6.7 Live Post-Trade Reconciliation

- Generated at: `2026-04-28T02:44:55.869401+00:00`
- Status: `live_post_trade_reconciled_with_warnings`
- Session id: `crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50`
- Strategy: `crypto_relative_strength_v1`
- Account: `binance-main-spot`

## Orders

- Expected orders: `1`
- Submitted orders: `1`
- Filled orders: `1`
- DB fills: `1`
- Session completed: `True`
- Missing submissions: `[]`
- Missing fills: `[]`

## Fill

- Gross quote notional: `49.266880`
- Gross base quantity: `0.00064`
- Net base quantity: `0.00063936`
- Average price: `76979.5`
- Fee: `0.00000064 BTC`
- Fee quote estimate: `0.049266880`

## Balances

- Status: `checked`
- Quote delta: `-49.26688000`
- Base delta: `0.00063936`
- Mismatches: `[]`

## Risk

- Total notional inside cap: `True`
- Order count inside cap: `True`
- Price deviation bps: `50.64150385439979568656706387`
- Price deviation inside cap: `True`

## Operational

- MQTT bridge failures: `4`
- Hummingbot stop observed: `True`
- Runner container status: `not_found`

## Tax Export

- Rows: `1`
- Gross quote notional: `49.266880`
- Fee quote estimate: `0.049266880`
- Cost basis quote estimate: `49.266880`
- FX source: `validation_only_not_tax_filing`

## Alerts

- `WARN` MQTT bridge unavailable: Hummingbot completed the live order, but the MQTT bridge failed to connect during the run.
- `WARN` Validation tax export: Tax export uses validation-only FX/source assumptions and is not final tax filing output.

## Artifacts

- event_jsonl: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`
- sqlite_db: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.sqlite`
- log_file: `/Users/albertlz/Downloads/private_proj/hummingbot/logs/logs_crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.log`
- candidate_package_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/package.json`
- runner_package_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.json`
- post_trade_report_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.json`
- post_trade_report_md: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.md`
- daily_report_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/daily_report.json`
- daily_report_md: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/daily_report.md`
- normalized_live_trades_jsonl: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/normalized_live_trades.jsonl`
- trade_tax_export_csv: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/trade_tax_export.csv`
- trade_tax_export_summary_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/trade_tax_export_summary.json`
- trade_tax_export_summary_md: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/trade_tax_export_summary.md`
