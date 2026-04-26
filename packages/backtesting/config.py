"""Backtest configuration loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from packages.data.csv_candle_source import parse_utc_datetime
from packages.data.market_data_service import CandleQuery
from packages.data.simple_yaml import load_simple_yaml


@dataclass(frozen=True, slots=True)
class SignalBacktestConfig:
    signal_type: str
    fast_window: int | None = None
    slow_window: int | None = None
    lookback_window: int | None = None
    top_n: int = 1
    min_momentum: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class PortfolioBacktestConfig:
    gross_target: Decimal
    max_symbol_weight: Decimal
    rebalance_threshold: Decimal
    volatility_target: Decimal | None = None
    volatility_window: int | None = None
    min_risk_scale: Decimal = Decimal("0")
    max_risk_scale: Decimal = Decimal("1")
    max_drawdown_stop: Decimal | None = None
    drawdown_stop_cooldown_bars: int = 0
    reset_drawdown_high_watermark_on_stop: bool = False
    risk_recovery_bars: int = 0
    min_order_notional: Decimal = Decimal("0")
    max_participation_rate: Decimal | None = None
    max_rebalance_turnover: Decimal | None = None


@dataclass(frozen=True, slots=True)
class RegimeFilterBacktestConfig:
    enabled: bool = False
    min_trend_strength: Decimal = Decimal("0")
    max_volatility: Decimal | None = None
    volatility_window: int | None = None


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    strategy_id: str
    exchange: str
    market_type: str
    trading_pairs: tuple[str, ...]
    interval: str
    start: datetime
    end: datetime
    initial_equity: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal
    signal: SignalBacktestConfig
    portfolio: PortfolioBacktestConfig
    regime_filter: RegimeFilterBacktestConfig = field(default_factory=RegimeFilterBacktestConfig)

    @property
    def allow_short(self) -> bool:
        return self.market_type in {"perpetual", "futures"}

    def candle_queries(self) -> tuple[CandleQuery, ...]:
        return tuple(
            CandleQuery(
                exchange=self.exchange,
                trading_pair=trading_pair,
                interval=self.interval,
                start=self.start,
                end=self.end,
            )
            for trading_pair in self.trading_pairs
        )


class BacktestConfigError(ValueError):
    """Raised when a backtest config is missing required fields."""


def load_backtest_config(strategy_dir: str | Path) -> BacktestConfig:
    directory = Path(strategy_dir)
    config = load_simple_yaml(directory / "config.yml")
    portfolio = load_simple_yaml(directory / "portfolio.yml")
    backtest = load_simple_yaml(directory / "backtest.yml")

    universe = _required_dict(config, "universe")
    signal = _required_dict(config, "signal")
    regime_filter = _optional_dict(config, "regime_filter")
    symbols = universe.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        raise BacktestConfigError("universe.symbols must be a non-empty list")

    return BacktestConfig(
        strategy_id=_required_str(config, "strategy_id"),
        exchange=_required_str(universe, "exchange"),
        market_type=str(universe.get("market_type", "spot")),
        trading_pairs=tuple(str(symbol) for symbol in symbols),
        interval=_required_str(config, "timeframe"),
        start=parse_utc_datetime(_required_str(backtest, "start")),
        end=parse_utc_datetime(_required_str(backtest, "end")),
        initial_equity=_required_decimal(backtest, "initial_equity"),
        fee_rate=_required_decimal(backtest, "fee_rate"),
        slippage_bps=_required_decimal(backtest, "slippage_bps"),
        signal=SignalBacktestConfig(
            signal_type=_required_str(signal, "type"),
            fast_window=_optional_int_or_none(signal, "fast_window"),
            slow_window=_optional_int_or_none(signal, "slow_window"),
            lookback_window=_optional_int_or_none(signal, "lookback_window"),
            top_n=_optional_int(signal, "top_n", default=1),
            min_momentum=_optional_decimal(signal, "min_momentum", default=Decimal("0")),
        ),
        portfolio=PortfolioBacktestConfig(
            gross_target=_required_decimal(portfolio, "gross_target"),
            max_symbol_weight=_required_decimal(portfolio, "max_symbol_weight"),
            rebalance_threshold=_required_decimal(portfolio, "rebalance_threshold"),
            volatility_target=_optional_decimal_or_none(portfolio, "volatility_target"),
            volatility_window=_optional_int_or_none(portfolio, "volatility_window"),
            min_risk_scale=_optional_decimal(
                portfolio,
                "min_risk_scale",
                default=Decimal("0"),
            ),
            max_risk_scale=_optional_decimal(
                portfolio,
                "max_risk_scale",
                default=Decimal("1"),
            ),
            max_drawdown_stop=_optional_decimal_or_none(portfolio, "max_drawdown_stop"),
            drawdown_stop_cooldown_bars=_optional_int(
                portfolio,
                "drawdown_stop_cooldown_bars",
                default=0,
            ),
            reset_drawdown_high_watermark_on_stop=_optional_bool(
                portfolio,
                "reset_drawdown_high_watermark_on_stop",
                default=False,
            ),
            risk_recovery_bars=_optional_int(
                portfolio,
                "risk_recovery_bars",
                default=0,
            ),
            min_order_notional=_optional_decimal(
                portfolio,
                "min_order_notional",
                default=Decimal("0"),
            ),
            max_participation_rate=_optional_decimal_or_none(
                portfolio,
                "max_participation_rate",
            ),
            max_rebalance_turnover=_optional_decimal_or_none(
                portfolio,
                "max_rebalance_turnover",
            ),
        ),
        regime_filter=RegimeFilterBacktestConfig(
            enabled=_optional_bool(regime_filter, "enabled", default=False),
            min_trend_strength=_optional_decimal(
                regime_filter,
                "min_trend_strength",
                default=Decimal("0"),
            ),
            max_volatility=_optional_decimal_or_none(regime_filter, "max_volatility"),
            volatility_window=_optional_int_or_none(regime_filter, "volatility_window"),
        ),
    )


def _required_dict(config: dict[str, object], key: str) -> dict[str, object]:
    value = _required_value(config, key)
    if not isinstance(value, dict):
        raise BacktestConfigError(f"{key} must be a mapping")
    return value


def _optional_dict(config: dict[str, object], key: str) -> dict[str, object]:
    value = config.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise BacktestConfigError(f"{key} must be a mapping")
    return value


def _required_value(config: dict[str, object], key: str) -> object:
    if key not in config:
        raise BacktestConfigError(f"missing required config key: {key}")
    return config[key]


def _required_str(config: dict[str, object], key: str) -> str:
    value = _required_value(config, key)
    if value is None:
        raise BacktestConfigError(f"{key} cannot be null")
    return str(value)


def _required_decimal(config: dict[str, object], key: str) -> Decimal:
    return Decimal(_required_str(config, key))


def _required_int(config: dict[str, object], key: str) -> int:
    return int(_required_str(config, key))


def _optional_decimal(config: dict[str, object], key: str, *, default: Decimal) -> Decimal:
    if key not in config or config[key] is None:
        return default
    return Decimal(str(config[key]))


def _optional_decimal_or_none(config: dict[str, object], key: str) -> Decimal | None:
    if key not in config or config[key] is None:
        return None
    return Decimal(str(config[key]))


def _optional_int_or_none(config: dict[str, object], key: str) -> int | None:
    if key not in config or config[key] is None:
        return None
    return int(str(config[key]))


def _optional_int(config: dict[str, object], key: str, *, default: int) -> int:
    if key not in config or config[key] is None:
        return default
    return int(str(config[key]))


def _optional_bool(config: dict[str, object], key: str, *, default: bool) -> bool:
    if key not in config or config[key] is None:
        return default
    value = config[key]
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"true", "1", "yes"}:
        return True
    if str(value).lower() in {"false", "0", "no"}:
        return False
    raise BacktestConfigError(f"{key} must be a boolean")
