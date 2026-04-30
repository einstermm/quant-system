# Phase 6.8 Live Cooldown Review

- Generated at: `2026-04-29T12:34:03.247655+00:00`
- Status: `live_cooldown_elapsed_with_warnings`
- Session id: `crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50`
- Strategy: `crypto_relative_strength_v1`
- Account: `binance-main-spot`

## Cooldown

- Completed at: `2026-04-28T02:34:33.175500+00:00`
- Minimum cooldown hours: `24`
- Elapsed hours: `33.99168670972222222222222222`
- Next review not before: `2026-04-29T02:34:33.175500+00:00`
- Cooldown elapsed: `True`

## Post Trade

- Post-trade status: `live_post_trade_reconciled_with_warnings`
- Submitted / filled / DB fills: `1 / 1 / 1`
- Gross quote notional: `49.266880`
- Net base quantity: `0.00063936`
- Balance mismatches: `[]`
- Risk caps passed: `True`

## Manual Checks

- Open orders check status: `confirmed_clean`
- Abnormal open orders found: `False`
- Checked at: `2026-04-28T02:55:38+00:00`
- Evidence: `Operator confirmed manual Binance spot open orders check completed; no abnormal open orders found.`

## Operational

- Runner container status: `docker_status_unavailable: failed to connect to the docker API at unix:///Users/albertlz/.docker/run/docker.sock; check if the path is correct and if the daemon is running: dial unix /Users/albertlz/.docker/run/docker.sock: connect: no such file or directory`
- Hummingbot container status: `docker_status_unavailable: failed to connect to the docker API at unix:///Users/albertlz/.docker/run/docker.sock; check if the path is correct and if the daemon is running: dial unix /Users/albertlz/.docker/run/docker.sock: connect: no such file or directory`
- Event log lines: `3022`
- Event log last event: `session_completed`
- Runner config armed: `False`

## Expansion Controls

- Allowlist locked: `True`
- Allowed pairs: `['BTC-USDT', 'ETH-USDT']`
- Max batch notional: `50`
- Max order notional: `50`
- Expansion allowed: `False`

## Alerts

- `WARN` Carried post-trade warning: MQTT bridge unavailable: Hummingbot completed the live order, but the MQTT bridge failed to connect during the run.
- `WARN` Carried post-trade warning: Validation tax export: Tax export uses validation-only FX/source assumptions and is not final tax filing output.

## Recommended Actions

- Cooldown elapsed; perform a manual operator review before any new activation.
- Do not expand beyond BTC-USDT / ETH-USDT or the 50 USDT low-funds cap.
- Open orders manual check is complete; keep the evidence with Phase 6.8 artifacts.
- Keep the Phase 6.6 one-shot runner config disarmed unless a new activation is approved.
- Fix or intentionally disable the MQTT bridge before any larger live session.
- Replace validation-only FX with a real CAD FX source before using exports for tax filing.

## Artifacts

- post_trade_report_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.json`
- event_jsonl: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50_events.jsonl`
- runner_config_yml: `/Users/albertlz/Downloads/private_proj/hummingbot/conf/scripts/crypto_relative_strength_v1_phase_6_6_live_one_batch_low_funds_50.yml`
- cooldown_review_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/cooldown_review.json`
- cooldown_review_md: `reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/cooldown_review.md`
- manual_open_orders_check_json: `reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/manual_open_orders_check.json`
