"""Unified market data query service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from packages.core.models import Candle
from packages.data.candle_repository import CandleRepository
from packages.data.data_quality import CandleQualityReport, build_candle_quality_report
from packages.data.timeframes import expected_interval_count, interval_to_timedelta


@dataclass(frozen=True, slots=True)
class CandleQuery:
    exchange: str
    trading_pair: str
    interval: str
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("start must be before end")

    @property
    def key(self) -> str:
        return f"{self.exchange}:{self.trading_pair}:{self.interval}"

    @property
    def inclusive_end(self) -> datetime:
        return self.end - interval_to_timedelta(self.interval)

    @property
    def expected_count(self) -> int:
        return expected_interval_count(start=self.start, end=self.end, interval=self.interval)


@dataclass(frozen=True, slots=True)
class CandleQueryResult:
    query: CandleQuery
    candles: tuple[Candle, ...]
    quality_report: CandleQualityReport

    @property
    def complete(self) -> bool:
        return self.quality_report.ok and len(self.candles) == self.query.expected_count

    @property
    def first_timestamp(self) -> datetime | None:
        if not self.candles:
            return None
        return self.candles[0].timestamp

    @property
    def last_timestamp(self) -> datetime | None:
        if not self.candles:
            return None
        return self.candles[-1].timestamp

    def summary(self) -> dict[str, object]:
        return {
            "key": self.query.key,
            "candles": len(self.candles),
            "expected": self.query.expected_count,
            "complete": self.complete,
            "quality_ok": self.quality_report.ok,
            "first_timestamp": self.first_timestamp.isoformat()
            if self.first_timestamp is not None
            else None,
            "last_timestamp": self.last_timestamp.isoformat()
            if self.last_timestamp is not None
            else None,
            "issues": [issue.to_dict() for issue in self.quality_report.issues],
        }


class MarketDataService:
    def __init__(self, candle_repository: CandleRepository) -> None:
        self._candle_repository = candle_repository

    def load_candles(self, query: CandleQuery) -> CandleQueryResult:
        candles = self._candle_repository.list(
            exchange=query.exchange,
            trading_pair=query.trading_pair,
            interval=query.interval,
            start=query.start,
            end=query.inclusive_end,
        )
        quality_report = build_candle_quality_report(
            candles,
            expected_start=query.start,
            expected_end=query.end,
        )
        return CandleQueryResult(query=query, candles=candles, quality_report=quality_report)

    def load_many(self, queries: tuple[CandleQuery, ...] | list[CandleQuery]) -> dict[str, CandleQueryResult]:
        return {query.key: self.load_candles(query) for query in queries}
