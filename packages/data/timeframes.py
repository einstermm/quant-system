"""Timeframe parsing helpers."""

from datetime import UTC, datetime, timedelta


_TIMEFRAME_TO_DELTA = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "8h": timedelta(hours=8),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
}


def interval_to_timedelta(interval: str) -> timedelta:
    try:
        return _TIMEFRAME_TO_DELTA[interval]
    except KeyError as exc:
        raise ValueError(f"unsupported interval: {interval}") from exc


def expected_interval_count(*, start: datetime, end: datetime, interval: str) -> int:
    if start >= end:
        raise ValueError("start must be before end")
    delta = interval_to_timedelta(interval)
    total_seconds = (end - start).total_seconds()
    return int(total_seconds // delta.total_seconds())


def floor_datetime_to_interval(value: datetime, interval: str) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    delta = interval_to_timedelta(interval)
    interval_seconds = int(delta.total_seconds())
    timestamp = int(value.astimezone(UTC).timestamp())
    floored_timestamp = timestamp - (timestamp % interval_seconds)
    return datetime.fromtimestamp(floored_timestamp, tz=UTC)
