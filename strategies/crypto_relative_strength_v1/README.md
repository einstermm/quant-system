# crypto_relative_strength_v1

BTC/ETH 相对强弱轮动策略，只用于离线研究。

- 信号：计算每个交易对过去 `lookback_window` 根 K 线的收益率。
- 选择：买入收益率最高且不低于 `min_momentum` 的资产。
- 约束：spot only，不做裸空。
- 当前 universe：BTC-USDT、ETH-USDT、BNB-USDT、SOL-USDT、XRP-USDT、ADA-USDT。
- 默认组合：选择 top 2，每个资产最大权重 `25%`，总目标风险暴露 `50%`。

## Phase 3.5 结果

默认全样本回测结果较差：总收益约 `-8.51%`，最大回撤约 `28.22%`，
换手约 `343x`，交易次数 `690`。

walk-forward 网格：

- `lookback_window`: `24,48,72,108,144`
- `min_momentum`: `0,0.02,0.05`
- fee: `0.0006`
- slippage: `2 bps`

结果：正收益折数 `6/10`，平均测试收益约 `2.84%`，中位测试收益约 `2.61%`，
最差测试收益约 `-13.59%`，最差测试回撤约 `14.64%`。

结论：这个方向比 MA baseline 更有研究价值，但尾部风险和换手仍未达标，不能进入
paper trading。

## Phase 3.6 结果

Phase 3.6 扩展到 6 个大流动性 spot 交易对，并扫描：

- `lookback_window`: `24,48,72,108,144`
- `top_n`: `1,2,3`
- `min_momentum`: `0,0.02,0.05`
- fee: `0.0006`
- slippage: `2 bps`

风险约束选择规则：

- `selection_min_return`: `0`
- `selection_max_drawdown`: `0.20`
- `selection_max_turnover`: `45`
- `selection_max_tail_loss`: `0.08`
- score penalty: drawdown `1`，turnover `0.001`，tail loss `2`

结果：正收益折数 `7/10`，平均测试收益约 `10.86%`，中位测试收益约 `4.43%`，
最差测试收益约 `-15.85%`，最差测试回撤约 `23.01%`。

结论：Phase 3.6 是目前最好的研究候选，但最差折亏损和回撤仍偏高。下一步应优先研究
组合级止损、波动率目标仓位和换手约束。

## Phase 3.7 结果

Phase 3.7 增加组合级风险覆盖层：

- realized volatility target: `0.010`
- volatility window: `72`
- global drawdown stop: `10%`
- risk-off cooldown: `36` 根 4h K 线
- per-rebalance turnover cap: `25%`

walk-forward 结果：正收益折数 `7/10`，平均测试收益约 `15.47%`，中位测试收益约
`2.66%`，最差测试收益约 `-4.79%`，最差测试回撤约 `10.62%`。

结论：风险覆盖层显著降低尾部亏损，是目前最接近可运行研究版本的候选。但收益分布仍
不够均匀，paper trading 前需要继续加入容量、成交量参与率和监控恢复流程。

## Phase 3.8 结果

Phase 3.8 增加执行容量约束：

- min order notional: `10 USDT`
- max participation rate: `2%`
- risk recovery bars: `18`

1 万 USDT 研究资金下，walk-forward 收益/回撤与 Phase 3.7 一致，说明容量约束没有
影响当前小资金回测。选中测试折最大观察参与率约 `0.0865%`，最小估算容量约
`23.12` 万 USDT。

100 万 USDT 压力测试触发参与率上限，`participation_capped_count=14`，被截断名义金额
约 `66.84` 万 USDT。结论：当前候选适合小资金 paper trading 研究，但资金规模扩大后
必须启用参与率和容量监控。

## Phase 3.9 结果

Phase 3.9 生成 paper readiness 报告、人工 Markdown 日报和 risk-off 恢复手册。

当前状态：`paper_ready_with_warnings`。

WARN：

- 平均收益受最好测试折影响较大。
- 选中测试折出现 risk-off，需要按恢复手册处理。
- 100 万 USDT 容量压力测试触发参与率上限。

结论：可以进入小资金 paper trading 准备，但必须保留 kill switch、启动前 readiness
检查、每日复核和 risk-off 恢复流程。live trading 继续禁止。

## Phase 4 结果

Phase 4 第一版接入本地 paper cycle，不连接 Hummingbot，不提交真实订单。

smoke run：

- readiness gate: `paper_ready_with_warnings`，通过显式人工允许。
- target weights: `BNB-USDT=0.25`，其他资产为 `0`。
- routed orders: `1`，approved: `1`。
- simulated fill: 买入 `BNB-USDT`，notional `500 USDT`，fee `0.5 USDT`。
- paper account: equity `1999.5 USDT`，gross exposure `500 USDT`。

当前结论：Phase 4 已具备单次本地 paper 下单闭环。下一步应进入 Phase 4.1，把该
cycle 接入定时循环并连续观察 24 小时。

## Phase 4.1 结果

Phase 4.1 已接入本地 paper observation loop。每轮 observation 会记录：

- 账户权益、现金、gross exposure 和持仓。
- 目标权重。
- 风险审批后的订单结果。
- K 线覆盖数量、预期数量和质量状态。

smoke observation：

- cycles: `2`
- status: `ok`
- routed orders: `1`
- approved orders: `1`
- rejected orders: `0`
- market data incomplete cycles: `0`
- last equity: `1999.5 USDT`

当前结论：本地 paper 运行链路、风控审批、ledger 重建和观察报告已跑通。下一步应接入
实时或准实时 K 线刷新，再运行完整 24 小时 observation。

## Phase 4.2 结果

Phase 4.2 已接入准实时 K 线刷新。开启 `--refresh-market-data` 后，observation loop
会在每轮 cycle 前刷新当前 universe 的 Binance spot 已收盘 K 线，并把刷新状态写入
`pre_cycle.market_data_refresh`。

刷新策略：

- 只使用 public K 线接口，不需要交易密钥。
- 默认延迟 `60` 秒确认 K 线收盘。
- 默认重取最近 `2` 根 K 线并 upsert 到 SQLite。
- 刷新失败时，本轮 paper cycle 失败并进入 observation report，不继续生成订单。

当前结论：系统已经具备准实时 paper observation 的数据刷新入口。下一步应启动真实
Binance public data 的 24 小时 observation，并复核刷新状态、数据完整性和风控结果。

public data smoke：

- runtime end: `2026-04-26T00:00:00+00:00`
- latest closed candle: `2026-04-25T20:00:00+00:00`
- per-symbol fetched candles: `692`
- target weights: `BTC-USDT=0.25`，`XRP-USDT=0.25`
- routed orders: `2`
- approved orders: `2`
- rejected orders: `0`
- paper equity: `1999.5 USDT`
