# Quant System

一套面向加密市场的机构级量化交易系统。系统把 Hummingbot 定位为执行基础设施：
连接交易所、订阅行情、维护订单状态、处理精度和复用 Strategy V2 Executor。自研部分负责
alpha、组合、账户级风控、回测研究、实验追踪、监控和报表。

## 当前阶段

Phase 1: 工程骨架和安全边界。

- 不连接真实交易所。
- 不读取真实 API key。
- 不执行真实下单。
- 先定义核心数据模型、风险决策接口、执行路由接口和 Hummingbot 适配边界。

## 模块边界

Hummingbot 直接承担：

- exchange connector
- WebSocket 行情
- 订单创建、撤销、状态追踪
- 余额、持仓、交易对精度和最小下单量
- PositionExecutor、TWAPExecutor、Grid/DCA/XEMM/Arbitrage Executor
- Docker、Dashboard、API

本系统自研：

- 策略信号和交易过滤
- 多策略、多币种、多账户组合管理
- 账户级全局风控和 kill switch
- 回测、数据仓库、实验记录
- 交易日志分析、风险 dashboard、监控告警
- 加拿大税务/报表导出基础数据

## 本地验证

```bash
./venv/bin/python main.py
./venv/bin/python -m unittest discover -s tests
```

## Phase 2 数据导入示例

```bash
./venv/bin/python -m packages.data.import_candles \
  --input data/samples/binance_1h_candles.csv \
  --quality-report /tmp/quant-system-data-quality.json
```

## 下一步

1. 先完成 `packages/core`、`packages/risk`、`packages/execution` 的接口稳定。
2. 再接入数据仓库和历史 K 线下载。
3. 然后做第一个只回测、不实盘的策略：`crypto_momentum_v1`。
4. 最后才把风险通过的订单意图转换为 Hummingbot Controller/Executor 配置。

详细路线见 `docs/roadmap.md`。
