# Phase 6.2 Credential And Allowlist Review

- Generated at: `2026-04-28T01:25:41.789073+00:00`
- Decision: `credential_allowlist_review_confirmed`
- Strategy: `crypto_relative_strength_v1`
- Connector: `binance`
- Account type: `main_account`
- Market type: `spot`

## Permissions

- Withdrawal: `disabled_confirmed_by_operator`
- Transfer: `disabled_confirmed_by_operator`
- Futures / margin / leverage: `disabled_confirmed_by_operator`
- Spot trading: `enabled_confirmed_by_operator`
- Read: `enabled_confirmed_by_operator`
- IP allowlist: `enabled_bound_to_runtime_public_ip_confirmed_by_operator`

## First Live Allowlist

- Trading pairs: `BTC-USDT, ETH-USDT`
- Quote asset: `USDT`
- Connector: `binance`
- Market type: `spot`

## Accepted Risk Limits

- Max order notional: `250`
- Max symbol notional: `500`
- Max gross notional: `1000`
- Max daily loss: `50`

## Note

API keys are not stored in `quant-system` and are not configured yet. Live connector configuration remains a later Phase 6.3 step.
