"""Backtest engine orchestration."""

from __future__ import annotations

from packages.backtesting.config import BacktestConfig
from packages.backtesting.result import BacktestResult
from packages.backtesting.simulator import MomentumBacktestSimulator
from packages.data.market_data_service import MarketDataService


class BacktestDataError(ValueError):
    """Raised when required backtest data is missing or incomplete."""


class BacktestEngine:
    def __init__(self, market_data_service: MarketDataService, *, code_version: str = "unknown") -> None:
        self._market_data_service = market_data_service
        self._code_version = code_version

    def run(self, config: BacktestConfig) -> BacktestResult:
        query_results = self._market_data_service.load_many(config.candle_queries())
        incomplete = [result for result in query_results.values() if not result.complete]
        if incomplete:
            keys = ", ".join(result.query.key for result in incomplete)
            raise BacktestDataError(f"incomplete backtest data for: {keys}")

        candles_by_symbol = {
            result.query.trading_pair: result.candles
            for result in query_results.values()
        }
        simulator = MomentumBacktestSimulator(code_version=self._code_version)
        return simulator.run(config=config, candles_by_symbol=candles_by_symbol)
