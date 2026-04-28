# Phase 6.2 Operator Signoff

- Generated at: `2026-04-28T01:29:13.700680+00:00`
- Decision: `operator_signoff_confirmed`
- Strategy: `crypto_relative_strength_v1`

## Confirmed Limits

- Max order notional: `250 USDT`
- Max symbol notional: `500 USDT`
- Max gross notional: `1000 USDT`
- Max daily loss: `50 USDT`
- Max drawdown: `5%`

## Scope

- First live allowlist: `BTC-USDT, ETH-USDT`
- First live run: `single small-funds live batch only`
- No automatic symbol or limit expansion.
- API configuration remains deferred to `Phase 6.3`.

## Emergency Action

- Execute kill switch / stop the Hummingbot container.
- After stopping, run daily report, reconciliation, and tax/trade export before any resume.

## Operator Statement

```text
我确认首次 live 最大单笔 250 USDT，
最大单币种 500 USDT，
最大总敞口 1000 USDT，
最大日亏损 50 USDT，
最大回撤 5%，
首次交易对仅 BTC-USDT、ETH-USDT，
首次只运行一批小资金 live batch，
不自动扩大交易对或额度，
如出现异常我会立即执行 kill switch / 停止 Hummingbot 容器，
停止后先做日报、reconciliation 和 tax/trade export，
API 配置留到 Phase 6.3。
```
