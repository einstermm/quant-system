"""Grid regime filter placeholder."""

from packages.features.market_regime import MarketRegime


def grid_allowed(regime: MarketRegime) -> bool:
    return regime in {MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY}
