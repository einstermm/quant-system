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

## Binance Download Example

Phase 2.1 默认下载 Binance spot public K 线，不需要 API key。系统内部交易对写作
`BTC-USDT`、`ETH-USDT`，请求 Binance 时会自动转换为 `BTCUSDT`、`ETHUSDT`。

```bash
./venv/bin/python -m packages.data.download_binance_candles \
  --symbols BTC-USDT ETH-USDT \
  --interval 4h \
  --start 2025-01-01 \
  --end 2026-01-01 \
  --output data/raw/binance_spot_BTC-ETH_4h_2025.csv \
  --quality-report data/reports/binance_spot_BTC-ETH_4h_2025_quality.json
```

时间范围按 `[start, end)` 处理。所以上面会下载从 `2025-01-01T00:00:00Z`
开始，到 `2025-12-31T20:00:00Z` 这一根 4h K 线为止的数据。

`data/raw/` 和 `data/reports/` 默认不进入 git，避免后续真实历史数据膨胀仓库。

默认会校验 TLS 证书。如果本机 Python 证书链异常导致 public data 下载失败，可以临时追加
`--insecure-skip-tls-verify`。这个参数只应用于公开行情下载，不应用于任何带 API key 的请求。

## SQLite Warehouse

Phase 2.2 使用 SQLite 作为第一版持久化数据仓库，不引入服务依赖，便于回测复现。

```bash
./venv/bin/python -m packages.data.load_candles_sqlite \
  --input data/raw/binance_spot_BTC-ETH_4h_2025.csv \
  --db data/warehouse/quant_system.sqlite \
  --quality-report data/reports/binance_spot_BTC-ETH_4h_2025_sqlite_load_quality.json
```

`candles` 表主键是：

```text
exchange, trading_pair, interval, timestamp
```

重复导入同一批数据会 upsert，不会制造重复 K 线。SQLite 数据库默认放在
`data/warehouse/`，该目录不进入 git。

## Strategy Data Query

Phase 2.3 增加统一查询入口，让回测模块后续只依赖 `MarketDataService`，不直接依赖
SQLite。

```bash
./venv/bin/python -m packages.data.query_strategy_candles \
  --strategy-dir strategies/crypto_momentum_v1 \
  --db data/warehouse/quant_system.sqlite
```

输出示例：

```text
strategy=crypto_momentum_v1
binance:BTC-USDT:4h candles=2190/2190 complete=True first=2025-01-01T00:00:00+00:00 last=2025-12-31T20:00:00+00:00 quality_ok=True
binance:ETH-USDT:4h candles=2190/2190 complete=True first=2025-01-01T00:00:00+00:00 last=2025-12-31T20:00:00+00:00 quality_ok=True
```

数据查询范围使用 `[start, end)`。例如 `start=2025-01-01`、`end=2026-01-01`、
`interval=4h` 时，最后一根 K 线开盘时间是 `2025-12-31T20:00:00+00:00`。

## Quality Checks

当前检查：

- 重复 timestamp。
- 原始数据乱序。
- 预期间隔缺口。
- 单根 K 线零成交量。
- 高低价范围异常。
- 相邻 close 大幅跳变。

后续接真实数据仓库时，`InMemoryCandleRepository` 会替换为 PostgreSQL 或对象存储实现，但上层接口保持不变。
