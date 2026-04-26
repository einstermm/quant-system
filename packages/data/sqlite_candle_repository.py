"""SQLite-backed candle repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from packages.core.models import Candle
from packages.data.csv_candle_source import parse_utc_datetime


class SQLiteCandleRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        self.initialize_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def __enter__(self) -> "SQLiteCandleRepository":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def initialize_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                exchange TEXT NOT NULL,
                trading_pair TEXT NOT NULL,
                interval TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open TEXT NOT NULL,
                high TEXT NOT NULL,
                low TEXT NOT NULL,
                close TEXT NOT NULL,
                volume TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (exchange, trading_pair, interval, timestamp)
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_candles_market_time
            ON candles (exchange, trading_pair, interval, timestamp)
            """
        )
        self._connection.commit()

    def add_many(self, candles: list[Candle] | tuple[Candle, ...]) -> None:
        rows = [
            (
                candle.exchange,
                candle.trading_pair,
                candle.interval,
                _timestamp_to_text(candle.timestamp),
                str(candle.open),
                str(candle.high),
                str(candle.low),
                str(candle.close),
                str(candle.volume),
            )
            for candle in candles
        ]
        self._connection.executemany(
            """
            INSERT INTO candles (
                exchange, trading_pair, interval, timestamp, open, high, low, close, volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(exchange, trading_pair, interval, timestamp)
            DO UPDATE SET
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                volume = excluded.volume,
                updated_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self._connection.commit()

    def list(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[Candle, ...]:
        where = [
            "exchange = ?",
            "trading_pair = ?",
            "interval = ?",
        ]
        params: list[str] = [exchange, trading_pair, interval]

        if start is not None:
            where.append("timestamp >= ?")
            params.append(_timestamp_to_text(start))
        if end is not None:
            where.append("timestamp <= ?")
            params.append(_timestamp_to_text(end))

        cursor = self._connection.execute(
            f"""
            SELECT exchange, trading_pair, interval, timestamp, open, high, low, close, volume
            FROM candles
            WHERE {' AND '.join(where)}
            ORDER BY timestamp ASC
            """,
            params,
        )
        return tuple(_row_to_candle(row) for row in cursor.fetchall())

    def latest(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
    ) -> Candle | None:
        cursor = self._connection.execute(
            """
            SELECT exchange, trading_pair, interval, timestamp, open, high, low, close, volume
            FROM candles
            WHERE exchange = ? AND trading_pair = ? AND interval = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (exchange, trading_pair, interval),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _row_to_candle(row)

    def count(
        self,
        *,
        exchange: str | None = None,
        trading_pair: str | None = None,
        interval: str | None = None,
    ) -> int:
        where: list[str] = []
        params: list[str] = []

        if exchange is not None:
            where.append("exchange = ?")
            params.append(exchange)
        if trading_pair is not None:
            where.append("trading_pair = ?")
            params.append(trading_pair)
        if interval is not None:
            where.append("interval = ?")
            params.append(interval)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        cursor = self._connection.execute(f"SELECT COUNT(*) FROM candles {where_sql}", params)
        return int(cursor.fetchone()[0])


def _timestamp_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _row_to_candle(row: sqlite3.Row) -> Candle:
    return Candle(
        exchange=row["exchange"],
        trading_pair=row["trading_pair"],
        interval=row["interval"],
        timestamp=parse_utc_datetime(row["timestamp"]),
        open=Decimal(row["open"]),
        high=Decimal(row["high"]),
        low=Decimal(row["low"]),
        close=Decimal(row["close"]),
        volume=Decimal(row["volume"]),
    )
