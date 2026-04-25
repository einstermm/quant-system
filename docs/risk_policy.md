# Risk Policy

第一版风险策略只做实盘前置拦截：

- 全局 kill switch。
- 单笔订单 notional 上限。
- 单币种风险暴露上限。
- 账户总 gross exposure 上限。
- 日亏损和最大回撤配置先保留在 `AccountRiskLimits`，后续接入权益曲线和交易日状态。

后续需要补充：

- reduce-only 模式。
- 多账户汇总风险。
- 交易所断连、订单状态异常、价格偏离和成交滑点异常处理。
- 人工审批模式。
