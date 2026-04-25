# Architecture

系统分成四条主线：

1. Research: 数据检查、特征、信号、回测、实验记录。
2. Portfolio and Risk: 组合目标、仓位调整、账户级限额、kill switch。
3. Execution: 标准化订单意图、执行策略、Hummingbot 适配、成交回报对账。
4. Observability: 日志、指标、告警、日报和策略报告。

Hummingbot 不承载 alpha 和账户级风控。它作为执行服务，被 `packages/adapters/hummingbot`
隔离在系统边界外。

## 安全原则

- 策略只能产生 `Signal`。
- 组合模块把信号转换为 `PortfolioTarget`。
- 执行策略把目标转换为 `OrderIntent`。
- `RiskEngine` 批准后，`OrderRouter` 才能调用执行适配器。
- Hummingbot API 客户端默认禁止 live submission。
