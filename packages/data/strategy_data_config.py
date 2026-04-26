"""Build market data queries from strategy configuration files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.data.csv_candle_source import parse_utc_datetime
from packages.data.market_data_service import CandleQuery
from packages.data.simple_yaml import load_simple_yaml


@dataclass(frozen=True, slots=True)
class StrategyDataConfig:
    strategy_id: str
    exchange: str
    trading_pairs: tuple[str, ...]
    interval: str
    start: object
    end: object

    def candle_queries(self) -> tuple[CandleQuery, ...]:
        start = parse_utc_datetime(str(self.start))
        end = parse_utc_datetime(str(self.end))
        return tuple(
            CandleQuery(
                exchange=self.exchange,
                trading_pair=trading_pair,
                interval=self.interval,
                start=start,
                end=end,
            )
            for trading_pair in self.trading_pairs
        )


class StrategyDataConfigError(ValueError):
    """Raised when a strategy config cannot define a data query."""


def load_strategy_data_config(strategy_dir: str | Path) -> StrategyDataConfig:
    directory = Path(strategy_dir)
    config = load_simple_yaml(directory / "config.yml")
    backtest = load_simple_yaml(directory / "backtest.yml")

    strategy_id = _required_str(config, "strategy_id")
    interval = _required_str(config, "timeframe")
    start = _required_value(backtest, "start")
    end = _required_value(backtest, "end")

    universe = config.get("universe")
    if isinstance(universe, dict):
        exchange = _required_str(universe, "exchange")
        raw_symbols = universe.get("symbols")
        if not isinstance(raw_symbols, list) or not raw_symbols:
            raise StrategyDataConfigError("universe.symbols must be a non-empty list")
        trading_pairs = tuple(str(symbol) for symbol in raw_symbols)
    else:
        exchange = "binance"
        trading_pairs = (_required_str(config, "symbol"),)

    return StrategyDataConfig(
        strategy_id=strategy_id,
        exchange=exchange,
        trading_pairs=trading_pairs,
        interval=interval,
        start=start,
        end=end,
    )


def _required_value(config: dict[str, object], key: str) -> object:
    if key not in config:
        raise StrategyDataConfigError(f"missing required config key: {key}")
    return config[key]


def _required_str(config: dict[str, object], key: str) -> str:
    value = _required_value(config, key)
    if value is None:
        raise StrategyDataConfigError(f"config key cannot be null: {key}")
    return str(value)
