"""Strategy-local signal wiring for crypto_momentum_v1."""

from packages.signals.trend_signal import MovingAverageTrendSignal


def build_signal() -> MovingAverageTrendSignal:
    return MovingAverageTrendSignal(
        strategy_id="crypto_momentum_v1",
        fast_window=24,
        slow_window=96,
    )
