# Phase 6.2 Live Activation Checklist

- Generated at: `2026-04-28T01:29:13.774801+00:00`
- Decision: `live_activation_ready`
- Session id: `crypto_relative_strength_v1_phase_6_2_live_activation_checklist`
- Strategy: `crypto_relative_strength_v1`

## Checklist

- `PASS` Phase 6.1 readiness available: Live readiness decision is live_preflight_ready_with_warnings. Evidence: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.json`
- `PASS` Daily report generated: Daily report status is daily_report_ready_with_warnings.
- `PASS` Trade tax export generated: Tax export status is tax_export_ready_with_warnings; rows=8, expected_filled_orders=8.
- `PASS` Strict live risk cap configured: max_order_notional=250; approved_initial_cap=250.
- `PASS` Live trading remains disabled: LIVE_TRADING_ENABLED must stay false until final manual signoff.
- `PASS` Global kill switch enabled: GLOBAL_KILL_SWITCH must stay true before activation.
- `PASS` External alert channel configured: Configure and verify at least one alert channel before live activation.
- `PASS` Credential scope reviewed: Confirm exchange keys are read-only/spot-trading scoped as intended, withdrawal disabled, and IP allowlist enabled where supported.
- `PASS` Exchange allowlist reviewed: Confirm allowed symbols, quote asset, account, and connector are exactly the Phase 6 activation target.
- `PASS` Operator activation signoff: Human operator signs off the first live order batch size, kill switch procedure, and rollback plan.

## Environment

- Live trading enabled: `False`
- Global kill switch: `True`
- Alert channel configured: `True`
- Exchange key env detected: `False`

## Risk Summary

`{'max_order_notional': '250', 'max_order_notional_decimal': '250', 'max_symbol_notional': '500', 'max_symbol_notional_decimal': '500', 'max_gross_notional': '1000', 'max_gross_notional_decimal': '1000', 'max_daily_loss': '50', 'max_daily_loss_decimal': '50', 'max_drawdown_pct': '0.05', 'max_drawdown_pct_decimal': '0.05'}`

## Activation Runbook

- Enable live trading only for the approved small-funds batch.
- Submit one controlled live batch and immediately rerun daily report, reconciliation, and tax export.
- If any alert fires, activate kill switch and follow the risk-off runbook.

## Artifacts

- live_readiness_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_1_live_readiness.json`
- daily_report_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.json`
- tax_export_summary_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export_summary.json`
- live_risk_yml: `strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml`
