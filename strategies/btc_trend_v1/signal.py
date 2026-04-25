"""Strategy-local signal wiring for btc_trend_v1."""

from packages.signals.trend_signal import MovingAverageTrendSignal


def build_signal() -> MovingAverageTrendSignal:
    return MovingAverageTrendSignal(
        strategy_id="btc_trend_v1",
        fast_window=24,
        slow_window=120,
    )
