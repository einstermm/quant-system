"""Simple market regime classification."""

from enum import Enum


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


def classify_regime(*, volatility: float, trend_strength: float) -> MarketRegime:
    if volatility >= 0.05:
        return MarketRegime.HIGH_VOLATILITY
    if trend_strength >= 0.02:
        return MarketRegime.TRENDING
    if volatility <= 0.01:
        return MarketRegime.LOW_VOLATILITY
    return MarketRegime.RANGING
