# Phase 6.1 Live Readiness Preflight

- Generated at: `2026-04-28T01:15:39.307842+00:00`
- Decision: `live_preflight_ready_with_warnings`
- Session id: `crypto_relative_strength_v1_phase_6_1_live_readiness`
- Strategy: `crypto_relative_strength_v1`

## Observation

- Decision: `hummingbot_observation_window_ready_with_warnings`
- Duration hours: `2.00000335`
- Events: `397`
- Submitted/Filled/Terminal: `8/8/8`
- Failed/Canceled/Unknown/Missing terminal: `0/0/0/0`

## Acceptance

- Decision: `sandbox_export_accepted_with_warnings`
- Event source: `hummingbot_export`
- Session gate: `sandbox_session_ready_with_warnings`

## Daily Report

- Status: `daily_report_ready_with_warnings`
- Filled orders: `8`
- Quote balance delta: `-986.23283690949096238402723`
- Total fee quote: `1.959705403998000008573058651`

## Risk And Environment

- Risk limits: `{'max_order_notional': '1000', 'max_order_notional_decimal': '1000', 'max_symbol_notional': '5000', 'max_symbol_notional_decimal': '5000', 'max_gross_notional': '5000', 'max_gross_notional_decimal': '5000', 'max_daily_loss': '250', 'max_daily_loss_decimal': '250', 'max_drawdown_pct': '0.10', 'max_drawdown_pct_decimal': '0.10'}`
- Live trading enabled: `False`
- Global kill switch: `True`
- Exchange key env detected: `False`
- Hummingbot API configured: `True`
- Alert channel configured: `True`

## Alerts

- `WARN` Observation review has warnings: Observation review decision is hummingbot_observation_window_ready_with_warnings.
- `WARN` Export acceptance has warnings: Export acceptance decision is sandbox_export_accepted_with_warnings.
- `WARN` Daily report has warnings: Daily report status is daily_report_ready_with_warnings.
- `WARN` Initial live order cap high: Configured max_order_notional is above the Phase 6.1 initial live cap; lower it before small-funds activation.
- `INFO` No exchange keys detected: No exchange credential environment variables were detected in this shell.
- `INFO` No live orders submitted: Phase 6.1 only builds readiness artifacts and does not submit orders.

## Activation Runbook

- Keep LIVE_TRADING_ENABLED=false until the manual activation checklist is signed off.
- Reduce initial live risk limits to the approved small-funds cap before activation.
- Configure an external alert channel and verify a test alert.
- Regenerate the Hummingbot handoff with a live connector only after credentials, allowlist, and kill switch are verified.
- Start with one small live order batch; rerun daily report, reconciliation, and tax export immediately after completion.

## Artifacts

- observation_review_json: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.json`
- acceptance_json: `reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_export_acceptance/acceptance.json`
- daily_report_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_1_daily_report.json`
- risk_yml: `strategies/crypto_relative_strength_v1/risk.yml`
