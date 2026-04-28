# Trade Tax Export Summary

- Generated at: `2026-04-27T17:47:00.167394+00:00`
- Status: `tax_export_ready_with_warnings`
- Strategy: `crypto_relative_strength_v1`
- Account: `paper-main-hummingbot`
- Rows: `8`
- Source: `hummingbot_export`
- Quote asset: `USDT`
- CAD FX rate: `1`
- FX source: `validation_only_not_tax_filing`

## Totals

- notional_quote: `1959.705403998000008573058651`
- fee_quote: `1.959705403998000008573058651`
- proceeds_quote: `486.4927936575390380904664264`
- cost_basis_quote: `1474.198356197597030474968153`
- proceeds_cad: `486.4927936575390380904664264`
- cost_basis_cad: `1474.198356197597030474968153`
- fees_cad: `1.959705403998000008573058651`

## Alerts

- `WARN` Validation FX source: FX source is suitable for pipeline validation only, not final tax filing.
- `WARN` ACB lot matching required: Sell rows need adjusted cost base lot matching before Canadian tax filing.

## Artifacts

- events_jsonl: `/Users/albertlz/Downloads/private_proj/hummingbot/data/crypto_relative_strength_v1_phase_5_10_r2_hummingbot_events.jsonl`
- tax_export_csv: `reports/live_readiness/crypto_relative_strength_v1_phase_6_2_trade_tax_export.csv`
