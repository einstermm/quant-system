# Strategy Lifecycle

策略上线顺序：

1. Research only: notebook 或脚本验证数据和信号。
2. Backtest: 固定数据版本、参数版本、手续费、滑点。
3. Paper trading: 不触发真实订单，只跑实时链路。
4. Sandbox trading: 交易所测试环境或极小资金账户。
5. Live trading: 需要明确启用 `LIVE_TRADING_ENABLED=true`，并关闭默认 kill switch。

每个策略必须有：

- `config.yml`
- `risk.yml`
- README
- 回测报告
- paper trading 观察记录

paper trading 观察记录至少包含：

- 每轮 cycle 的账户权益、持仓和目标权重。
- 每个订单意图的风控状态和拒绝原因。
- 数据覆盖和质量状态。
- observation summary JSON 与 Markdown report。
