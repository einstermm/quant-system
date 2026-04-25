"""CSV candle loader.

Expected columns:
timestamp, exchange, trading_pair, interval, open, high, low, close, volume
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from packages.core.models import Candle


REQUIRED_COLUMNS = (
    "timestamp",
    "exchange",
    "trading_pair",
    "interval",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class CandleCSVFormatError(ValueError):
    """Raised when a candle CSV file cannot be parsed."""


@dataclass(frozen=True, slots=True)
class CandleCSVRowError:
    line_number: int
    message: str


@dataclass(frozen=True, slots=True)
class CandleCSVReadResult:
    path: Path
    candles: tuple[Candle, ...]
    row_errors: tuple[CandleCSVRowError, ...]


def parse_utc_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decimal_from_row(row: dict[str, str], column: str) -> Decimal:
    try:
        return Decimal(row[column])
    except (InvalidOperation, KeyError) as exc:
        raise CandleCSVFormatError(f"invalid decimal in column {column}") from exc


def read_candles_csv(path: str | Path, *, strict: bool = True) -> CandleCSVReadResult:
    csv_path = Path(path)
    candles: list[Candle] = []
    row_errors: list[CandleCSVRowError] = []

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing_columns = sorted(set(REQUIRED_COLUMNS) - set(reader.fieldnames or ()))
        if missing_columns:
            raise CandleCSVFormatError(f"missing required columns: {', '.join(missing_columns)}")

        for line_number, row in enumerate(reader, start=2):
            try:
                candles.append(
                    Candle(
                        exchange=row["exchange"].strip(),
                        trading_pair=row["trading_pair"].strip(),
                        interval=row["interval"].strip(),
                        timestamp=parse_utc_datetime(row["timestamp"]),
                        open=_decimal_from_row(row, "open"),
                        high=_decimal_from_row(row, "high"),
                        low=_decimal_from_row(row, "low"),
                        close=_decimal_from_row(row, "close"),
                        volume=_decimal_from_row(row, "volume"),
                    )
                )
            except (KeyError, ValueError) as exc:
                row_errors.append(CandleCSVRowError(line_number, str(exc)))

    if strict and row_errors:
        first_error = row_errors[0]
        raise CandleCSVFormatError(f"line {first_error.line_number}: {first_error.message}")

    candles.sort(key=lambda candle: (candle.exchange, candle.trading_pair, candle.interval, candle.timestamp))
    return CandleCSVReadResult(csv_path, tuple(candles), tuple(row_errors))


def write_candles_csv(candles: tuple[Candle, ...] | list[Candle], path: str | Path) -> Path:
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_candles = sorted(
        candles,
        key=lambda candle: (candle.exchange, candle.trading_pair, candle.interval, candle.timestamp),
    )

    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for candle in sorted_candles:
            writer.writerow(
                {
                    "timestamp": candle.timestamp.isoformat(),
                    "exchange": candle.exchange,
                    "trading_pair": candle.trading_pair,
                    "interval": candle.interval,
                    "open": str(candle.open),
                    "high": str(candle.high),
                    "low": str(candle.low),
                    "close": str(candle.close),
                    "volume": str(candle.volume),
                }
            )

    return csv_path
