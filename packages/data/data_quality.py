"""Data quality checks and report serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from packages.core.models import Candle
from packages.data.timeframes import interval_to_timedelta


@dataclass(frozen=True, slots=True)
class CandleQualityIssue:
    code: str
    severity: str
    message: str
    exchange: str
    trading_pair: str
    interval: str
    timestamp: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "exchange": self.exchange,
            "trading_pair": self.trading_pair,
            "interval": self.interval,
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
        }


@dataclass(frozen=True, slots=True)
class CandleQualityReport:
    candles_checked: int
    groups_checked: int
    issues: tuple[CandleQualityIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {
            "candles_checked": self.candles_checked,
            "groups_checked": self.groups_checked,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def validate_candle_sequence(candles: tuple[Candle, ...] | list[Candle]) -> list[str]:
    report = build_candle_quality_report(candles)
    return [issue.message for issue in report.issues]


def build_candle_quality_report(
    candles: tuple[Candle, ...] | list[Candle],
    *,
    expected_start: datetime | None = None,
    expected_end: datetime | None = None,
    max_close_change_pct: Decimal = Decimal("0.50"),
    max_range_pct: Decimal = Decimal("1.00"),
) -> CandleQualityReport:
    grouped: dict[tuple[str, str, str], list[Candle]] = {}
    issues: list[CandleQualityIssue] = []

    for candle in candles:
        key = (candle.exchange, candle.trading_pair, candle.interval)
        grouped.setdefault(key, []).append(candle)

        if candle.volume == Decimal("0"):
            issues.append(
                _issue("zero_volume", "warning", "candle volume is zero", candle)
            )

        range_pct = (candle.high - candle.low) / candle.close
        if range_pct > max_range_pct:
            issues.append(
                _issue(
                    "wide_price_range",
                    "warning",
                    f"high/low range {range_pct} exceeds {max_range_pct}",
                    candle,
                )
            )

    for group_key, group_candles in grouped.items():
        exchange, trading_pair, interval = group_key
        seen_timestamps: set[datetime] = set()
        previous_original_timestamp: datetime | None = None

        for candle in group_candles:
            if candle.timestamp in seen_timestamps:
                issues.append(_issue("duplicate_timestamp", "error", "duplicate candle timestamp", candle))
            seen_timestamps.add(candle.timestamp)

            if previous_original_timestamp is not None and candle.timestamp < previous_original_timestamp:
                issues.append(_issue("out_of_order", "error", "candles are not sorted by timestamp", candle))
            previous_original_timestamp = candle.timestamp

        expected_delta = interval_to_timedelta(interval)
        sorted_group = sorted(group_candles, key=lambda candle: candle.timestamp)

        if expected_start is not None and sorted_group[0].timestamp > expected_start:
            issues.append(
                CandleQualityIssue(
                    code="missing_start",
                    severity="error",
                    message=(
                        f"first candle {sorted_group[0].timestamp.isoformat()} is after "
                        f"expected start {expected_start.isoformat()}"
                    ),
                    exchange=exchange,
                    trading_pair=trading_pair,
                    interval=interval,
                    timestamp=sorted_group[0].timestamp,
                )
            )

        if expected_end is not None:
            last_expected_open = expected_end - expected_delta
            if sorted_group[-1].timestamp < last_expected_open:
                issues.append(
                    CandleQualityIssue(
                        code="missing_end",
                        severity="error",
                        message=(
                            f"last candle {sorted_group[-1].timestamp.isoformat()} is before "
                            f"expected final open {last_expected_open.isoformat()}"
                        ),
                        exchange=exchange,
                        trading_pair=trading_pair,
                        interval=interval,
                        timestamp=sorted_group[-1].timestamp,
                    )
                )

        for previous, current in zip(sorted_group, sorted_group[1:]):
            actual_delta = current.timestamp - previous.timestamp
            if actual_delta > expected_delta:
                issues.append(
                    CandleQualityIssue(
                        code="missing_candle",
                        severity="error",
                        message=(
                            f"gap from {previous.timestamp.isoformat()} to "
                            f"{current.timestamp.isoformat()} exceeds expected {expected_delta}"
                        ),
                        exchange=exchange,
                        trading_pair=trading_pair,
                        interval=interval,
                        timestamp=current.timestamp,
                    )
                )

            close_change = abs(current.close / previous.close - Decimal("1"))
            if close_change > max_close_change_pct:
                issues.append(
                    _issue(
                        "large_close_change",
                        "warning",
                        f"close change {close_change} exceeds {max_close_change_pct}",
                        current,
                    )
                )

    return CandleQualityReport(
        candles_checked=len(candles),
        groups_checked=len(grouped),
        issues=tuple(issues),
    )


def write_quality_report(report: CandleQualityReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def _issue(code: str, severity: str, message: str, candle: Candle) -> CandleQualityIssue:
    return CandleQualityIssue(
        code=code,
        severity=severity,
        message=message,
        exchange=candle.exchange,
        trading_pair=candle.trading_pair,
        interval=candle.interval,
        timestamp=candle.timestamp,
    )
