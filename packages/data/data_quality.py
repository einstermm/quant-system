"""Basic data quality checks."""

from packages.core.models import Candle


def validate_candle_sequence(candles: tuple[Candle, ...] | list[Candle]) -> list[str]:
    issues: list[str] = []
    previous_timestamp = None
    seen_timestamps = set()

    for candle in candles:
        if candle.timestamp in seen_timestamps:
            issues.append(f"duplicate candle timestamp: {candle.timestamp.isoformat()}")
        seen_timestamps.add(candle.timestamp)

        if previous_timestamp is not None and candle.timestamp < previous_timestamp:
            issues.append("candles are not sorted by timestamp")
        previous_timestamp = candle.timestamp

    return issues
