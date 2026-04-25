"""Timeframe parsing helpers."""

from datetime import timedelta


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
