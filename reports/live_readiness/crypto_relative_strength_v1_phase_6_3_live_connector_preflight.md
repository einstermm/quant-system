# Phase 6.3 Live Connector Preflight

- Generated at: `2026-04-28T01:53:25.928297+00:00`
- Decision: `live_connector_preflight_ready`
- Session id: `crypto_relative_strength_v1_phase_6_3_live_connector_preflight`
- Strategy: `crypto_relative_strength_v1`
- Connector: `binance`
- Market type: `spot`
- Allowed pairs: `BTC-USDT, ETH-USDT`

## Connector Status

- Hummingbot root: `/Users/albertlz/Downloads/private_proj/hummingbot`
- Host connector path: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors/binance.yml`
- Container connector path: `/home/hummingbot/conf/connectors/binance.yml`
- Expected connector configured: `True`
- Required secret fields: `binance_api_key, binance_api_secret`
- Missing secret fields: `none`
- Secret values redacted: `True`

## Connector Configs

| Account | Connector | Risk | Secret Fields | Path |
| --- | --- | --- | --- | --- |
| `unknown` | `binance` | `live` | `binance_api_key, binance_api_secret` | `/Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors/binance.yml` |

## Checklist

- `PASS` Phase 6.2 activation checklist ready: Activation checklist decision is live_activation_ready.
- `PASS` Credential and exchange allowlist reviewed: Credential review decision is credential_allowlist_review_confirmed.
- `PASS` Operator signoff recorded: Operator signoff decision is operator_signoff_confirmed.
- `PASS` Connector scope matches first live target: Credential review connector=binance, market_type=spot.
- `PASS` First live symbol allowlist matches: Credential pairs=('BTC-USDT', 'ETH-USDT'); operator pairs=('BTC-USDT', 'ETH-USDT').
- `PASS` Live risk config matches operator signoff: Strict live risk file must match the Phase 6.2 operator signoff.
- `PASS` No unexpected live connector configs mounted: Only the approved first-live connector may be mounted for Phase 6.3.
- `PASS` Expected live connector config exists: Configure this only inside Hummingbot CLI; values remain redacted. Evidence: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/connectors/binance.yml`
- `PASS` Expected connector secret field names detected: The report records field names only and never emits credential values.
- `PASS` Live trading remains disabled in quant-system: LIVE_TRADING_ENABLED must remain false until the final live batch activation step.
- `PASS` Global kill switch remains enabled: GLOBAL_KILL_SWITCH must remain true before final live batch activation.
- `PASS` External alert channel configured: At least one external alert channel must be configured before live connector use.
- `PASS` Exchange keys are not stored in quant-system env: Real exchange credentials belong in Hummingbot connector config.

## Environment

- Live trading enabled: `False`
- Global kill switch: `True`
- Alert channel configured: `True`
- Exchange key env detected: `False`

## Alerts

- `INFO` Secrets redacted: Phase 6.3 reports connector field names only; credential values are never emitted.

## Runbook

- Keep LIVE_TRADING_ENABLED=false and GLOBAL_KILL_SWITCH=true until live activation.
- Do not expand symbols or risk limits beyond BTC-USDT and ETH-USDT.
- Proceed to the next phase for final one-batch live activation planning.

## Artifacts

- activation_checklist_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.json`
- credential_allowlist_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_credential_allowlist_review.json`
- operator_signoff_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_operator_signoff.json`
- live_risk_yml: `strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml`
