# Data Layer

Phase 2 先支持本地 CSV 导入。这个选择是为了先把数据模型、质量检查和仓库查询链路跑通，不把早期系统稳定性绑在公网 API 上。

## Candle CSV Schema

必需列：

```text
timestamp,exchange,trading_pair,interval,open,high,low,close,volume
```

时间使用 ISO-8601，建议带 UTC offset：

```text
2024-01-01T00:00:00+00:00
```

## Import Example

```bash
./venv/bin/python -m packages.data.import_candles \
  --input data/samples/binance_1h_candles.csv \
  --quality-report /tmp/quant-system-data-quality.json
```

这条命令会：

- 读取 BTC-USDT、ETH-USDT 的 1h K 线样例。
- 写入内存 `CandleRepository`。
- 生成 JSON 数据质量报告。

## Quality Checks

当前检查：

- 重复 timestamp。
- 原始数据乱序。
- 预期间隔缺口。
- 单根 K 线零成交量。
- 高低价范围异常。
- 相邻 close 大幅跳变。

后续接真实数据仓库时，`InMemoryCandleRepository` 会替换为 PostgreSQL 或对象存储实现，但上层接口保持不变。
