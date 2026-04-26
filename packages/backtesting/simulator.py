"""Historical bar replay simulator."""

from __future__ import annotations

from decimal import Decimal
from statistics import pstdev

from packages.backtesting.config import BacktestConfig
from packages.backtesting.cost_model import percentage_fee
from packages.backtesting.metrics import average, max_drawdown, tail_loss, total_return, turnover
from packages.backtesting.result import BacktestResult, BacktestTrade, EquityPoint, decimal_to_str
from packages.backtesting.slippage_model import bps_slippage_price
from packages.core.enums import SignalDirection
from packages.core.models import Candle
from packages.features.indicators import simple_moving_average
from packages.features.volatility import close_to_close_volatility


class Simulator:
    def run(self) -> None:
        raise NotImplementedError("use MomentumBacktestSimulator for crypto_momentum_v1")


class MomentumBacktestSimulator:
    def __init__(self, *, code_version: str = "unknown") -> None:
        self._code_version = code_version

    def run(
        self,
        *,
        config: BacktestConfig,
        candles_by_symbol: dict[str, tuple[Candle, ...]],
    ) -> BacktestResult:
        _validate_candles(config, candles_by_symbol)
        if config.signal.signal_type not in {"moving_average_trend", "relative_strength_rotation"}:
            raise ValueError(f"unsupported signal type: {config.signal.signal_type}")

        cash = config.initial_equity
        positions = {symbol: Decimal("0") for symbol in config.trading_pairs}
        trades: list[BacktestTrade] = []
        equity_curve = [EquityPoint(config.start, config.initial_equity)]
        total_fees = Decimal("0")
        total_traded_notional = Decimal("0")
        risk_scale_values: list[Decimal] = []
        high_watermark = config.initial_equity
        risk_off_bars_remaining = 0
        recovery_bars_remaining = 0
        risk_off_bar_count = 0
        recovery_bar_count = 0
        drawdown_stop_count = 0
        min_order_skipped_count = 0
        min_order_skipped_notional = Decimal("0")
        participation_capped_count = 0
        participation_capped_notional = Decimal("0")
        max_observed_participation_rate = Decimal("0")
        symbols = config.trading_pairs
        reference_symbol = symbols[0]
        bar_count = len(candles_by_symbol[reference_symbol])

        for signal_index in range(_warmup_window(config) - 1, bar_count - 1):
            execution_index = signal_index + 1
            execution_time = candles_by_symbol[reference_symbol][execution_index].timestamp
            open_prices = {
                symbol: candles_by_symbol[symbol][execution_index].open
                for symbol in symbols
            }
            close_prices = {
                symbol: candles_by_symbol[symbol][execution_index].close
                for symbol in symbols
            }
            equity_at_open = cash + sum(
                positions[symbol] * open_prices[symbol]
                for symbol in symbols
            )
            target_weights = _target_weights(config, candles_by_symbol, signal_index)
            target_weights, risk_scale = _apply_volatility_target(
                config,
                candles_by_symbol,
                signal_index,
                target_weights,
            )

            if risk_off_bars_remaining > 0:
                target_weights = _zero_weights(symbols)
                risk_scale = Decimal("0")
                risk_off_bars_remaining -= 1
                risk_off_bar_count += 1
            elif recovery_bars_remaining > 0:
                recovery_scale = _recovery_scale(
                    recovery_bars_remaining=recovery_bars_remaining,
                    recovery_bars=config.portfolio.risk_recovery_bars,
                )
                target_weights = _scale_weights(target_weights, recovery_scale)
                risk_scale *= recovery_scale
                recovery_bars_remaining -= 1
                recovery_bar_count += 1
            risk_scale_values.append(risk_scale)

            delta_notional_by_symbol: dict[str, Decimal] = {}
            for symbol in symbols:
                target_weight = target_weights[symbol]
                target_notional = equity_at_open * target_weight
                current_notional = positions[symbol] * open_prices[symbol]
                delta_notional = target_notional - current_notional

                if _below_rebalance_threshold(
                    delta_notional=delta_notional,
                    equity=equity_at_open,
                    threshold=config.portfolio.rebalance_threshold,
                ):
                    delta_notional_by_symbol[symbol] = Decimal("0")
                    continue
                delta_notional_by_symbol[symbol] = delta_notional

            delta_notional_by_symbol = _cap_rebalance_turnover(
                delta_notional_by_symbol,
                equity=equity_at_open,
                max_turnover=config.portfolio.max_rebalance_turnover,
            )

            for symbol, delta_notional in delta_notional_by_symbol.items():
                if delta_notional == Decimal("0"):
                    continue
                side_sign = 1 if delta_notional > Decimal("0") else -1
                execution_price = bps_slippage_price(
                    reference_price=open_prices[symbol],
                    side_sign=side_sign,
                    slippage_bps=config.slippage_bps,
                )
                capped_delta = _cap_participation(
                    delta_notional=delta_notional,
                    execution_price=execution_price,
                    candle_volume=candles_by_symbol[symbol][execution_index].volume,
                    max_participation_rate=config.portfolio.max_participation_rate,
                )
                if capped_delta != delta_notional:
                    participation_capped_count += 1
                    participation_capped_notional += abs(delta_notional) - abs(capped_delta)
                    delta_notional = capped_delta
                if _below_min_order_notional(
                    delta_notional=delta_notional,
                    min_order_notional=config.portfolio.min_order_notional,
                ):
                    min_order_skipped_count += 1
                    min_order_skipped_notional += abs(delta_notional)
                    continue

                quantity_delta = delta_notional / execution_price
                notional = abs(quantity_delta * execution_price)
                fee = percentage_fee(notional=notional, fee_rate=config.fee_rate)
                max_observed_participation_rate = max(
                    max_observed_participation_rate,
                    _participation_rate(
                        notional=notional,
                        execution_price=execution_price,
                        candle_volume=candles_by_symbol[symbol][execution_index].volume,
                    ),
                )

                if quantity_delta > Decimal("0"):
                    cash -= notional + fee
                    side = "buy"
                else:
                    cash += notional - fee
                    side = "sell"

                positions[symbol] += quantity_delta
                total_fees += fee
                total_traded_notional += notional
                trades.append(
                    BacktestTrade(
                        timestamp=execution_time,
                        symbol=symbol,
                        side=side,
                        quantity=abs(quantity_delta),
                        price=execution_price,
                        notional=notional,
                        fee=fee,
                        target_weight=(positions[symbol] * open_prices[symbol]) / equity_at_open,
                    )
                )

            equity_at_close = cash + sum(
                positions[symbol] * close_prices[symbol]
                for symbol in symbols
            )
            equity_curve.append(EquityPoint(execution_time, equity_at_close))
            high_watermark = max(high_watermark, equity_at_close)
            if _drawdown_stop_triggers(
                equity=equity_at_close,
                high_watermark=high_watermark,
                threshold=config.portfolio.max_drawdown_stop,
            ):
                if risk_off_bars_remaining == 0:
                    drawdown_stop_count += 1
                risk_off_bars_remaining = max(
                    risk_off_bars_remaining,
                    config.portfolio.drawdown_stop_cooldown_bars,
                )
                recovery_bars_remaining = config.portfolio.risk_recovery_bars
                if config.portfolio.reset_drawdown_high_watermark_on_stop:
                    high_watermark = equity_at_close

        equity_values = tuple(point.equity for point in equity_curve)
        avg_equity = average(equity_values)
        end_equity = equity_curve[-1].equity

        return BacktestResult(
            strategy_id=config.strategy_id,
            code_version=self._code_version,
            parameters={
                "exchange": config.exchange,
                "market_type": config.market_type,
                "trading_pairs": list(config.trading_pairs),
                "interval": config.interval,
                "start": config.start.isoformat(),
                "end": config.end.isoformat(),
                "initial_equity": decimal_to_str(config.initial_equity),
                "fee_rate": decimal_to_str(config.fee_rate),
                "slippage_bps": decimal_to_str(config.slippage_bps),
                "signal_type": config.signal.signal_type,
                "fast_window": config.signal.fast_window,
                "slow_window": config.signal.slow_window,
                "lookback_window": config.signal.lookback_window,
                "top_n": config.signal.top_n,
                "min_momentum": decimal_to_str(config.signal.min_momentum),
                "gross_target": decimal_to_str(config.portfolio.gross_target),
                "max_symbol_weight": decimal_to_str(config.portfolio.max_symbol_weight),
                "rebalance_threshold": decimal_to_str(config.portfolio.rebalance_threshold),
                "volatility_target": decimal_to_str(config.portfolio.volatility_target)
                if config.portfolio.volatility_target is not None
                else None,
                "volatility_window": config.portfolio.volatility_window,
                "min_risk_scale": decimal_to_str(config.portfolio.min_risk_scale),
                "max_risk_scale": decimal_to_str(config.portfolio.max_risk_scale),
                "max_drawdown_stop": decimal_to_str(config.portfolio.max_drawdown_stop)
                if config.portfolio.max_drawdown_stop is not None
                else None,
                "drawdown_stop_cooldown_bars": config.portfolio.drawdown_stop_cooldown_bars,
                "reset_drawdown_high_watermark_on_stop": (
                    config.portfolio.reset_drawdown_high_watermark_on_stop
                ),
                "risk_recovery_bars": config.portfolio.risk_recovery_bars,
                "min_order_notional": decimal_to_str(config.portfolio.min_order_notional),
                "max_participation_rate": decimal_to_str(config.portfolio.max_participation_rate)
                if config.portfolio.max_participation_rate is not None
                else None,
                "max_rebalance_turnover": decimal_to_str(config.portfolio.max_rebalance_turnover)
                if config.portfolio.max_rebalance_turnover is not None
                else None,
                "allow_short": config.allow_short,
                "regime_filter_enabled": config.regime_filter.enabled,
                "regime_filter_min_trend_strength": decimal_to_str(
                    config.regime_filter.min_trend_strength
                ),
                "regime_filter_max_volatility": decimal_to_str(config.regime_filter.max_volatility)
                if config.regime_filter.max_volatility is not None
                else None,
                "regime_filter_volatility_window": config.regime_filter.volatility_window,
            },
            data={
                "symbols": {
                    symbol: {
                        "candles": len(candles_by_symbol[symbol]),
                        "first_timestamp": candles_by_symbol[symbol][0].timestamp.isoformat(),
                        "last_timestamp": candles_by_symbol[symbol][-1].timestamp.isoformat(),
                    }
                    for symbol in symbols
                }
            },
            metrics={
                "start_equity": config.initial_equity,
                "end_equity": end_equity,
                "total_return": total_return(
                    start_equity=config.initial_equity,
                    end_equity=end_equity,
                ),
                "max_drawdown": max_drawdown(equity_values),
                "tail_loss": tail_loss(equity_values),
                "total_fees": total_fees,
                "traded_notional": total_traded_notional,
                "turnover": turnover(
                    traded_notional=total_traded_notional,
                    average_equity=avg_equity,
                ),
                "trade_count": len(trades),
                "bars": len(equity_curve) - 1,
                "average_risk_scale": average(risk_scale_values)
                if risk_scale_values
                else Decimal("1"),
                "risk_off_bars": risk_off_bar_count,
                "recovery_bars": recovery_bar_count,
                "drawdown_stop_count": drawdown_stop_count,
                "min_order_skipped_count": min_order_skipped_count,
                "min_order_skipped_notional": min_order_skipped_notional,
                "participation_capped_count": participation_capped_count,
                "participation_capped_notional": participation_capped_notional,
                "max_observed_participation_rate": max_observed_participation_rate,
                "estimated_participation_capacity_equity": _estimated_capacity_equity(
                    initial_equity=config.initial_equity,
                    max_participation_rate=config.portfolio.max_participation_rate,
                    max_observed_participation_rate=max_observed_participation_rate,
                ),
            },
            equity_curve=tuple(equity_curve),
            trades=tuple(trades),
        )


def _zero_weights(symbols: tuple[str, ...]) -> dict[str, Decimal]:
    return {symbol: Decimal("0") for symbol in symbols}


def _scale_weights(weights: dict[str, Decimal], scale: Decimal) -> dict[str, Decimal]:
    return {
        symbol: weight * scale
        for symbol, weight in weights.items()
    }


def _recovery_scale(*, recovery_bars_remaining: int, recovery_bars: int) -> Decimal:
    if recovery_bars <= 0:
        return Decimal("1")
    completed = recovery_bars - recovery_bars_remaining + 1
    return Decimal(completed) / Decimal(recovery_bars)


def _target_weights(
    config: BacktestConfig,
    candles_by_symbol: dict[str, tuple[Candle, ...]],
    signal_index: int,
) -> dict[str, Decimal]:
    if config.signal.signal_type == "relative_strength_rotation":
        return _relative_strength_target_weights(config, candles_by_symbol, signal_index)

    if config.signal.fast_window is None or config.signal.slow_window is None:
        raise ValueError("moving_average_trend requires fast_window and slow_window")
    directions = {
        symbol: _signal_features(
            candles_by_symbol[symbol],
            signal_index=signal_index,
            fast_window=config.signal.fast_window,
            slow_window=config.signal.slow_window,
            volatility_window=config.regime_filter.volatility_window or config.signal.slow_window,
        )
        for symbol in config.trading_pairs
    }
    active_symbols = [
        symbol
        for symbol, features in directions.items()
        if _direction_can_trade(features["direction"], config.allow_short)
        and _regime_filter_allows(
            trend_strength=features["trend_strength"],
            volatility=features["volatility"],
            config=config,
        )
    ]
    weights = {symbol: Decimal("0") for symbol in config.trading_pairs}
    if not active_symbols:
        return weights

    equal_weight = config.portfolio.gross_target / Decimal(len(active_symbols))
    capped_weight = min(equal_weight, config.portfolio.max_symbol_weight)
    for symbol in active_symbols:
        if directions[symbol]["direction"] is SignalDirection.SHORT:
            weights[symbol] = -capped_weight
        else:
            weights[symbol] = capped_weight
    return weights


def _apply_volatility_target(
    config: BacktestConfig,
    candles_by_symbol: dict[str, tuple[Candle, ...]],
    signal_index: int,
    target_weights: dict[str, Decimal],
) -> tuple[dict[str, Decimal], Decimal]:
    target = config.portfolio.volatility_target
    window = config.portfolio.volatility_window
    if target is None or window is None:
        return target_weights, Decimal("1")
    if all(weight == Decimal("0") for weight in target_weights.values()):
        return target_weights, Decimal("0")

    realized = _portfolio_volatility(
        candles_by_symbol=candles_by_symbol,
        signal_index=signal_index,
        target_weights=target_weights,
        window=window,
    )
    if realized <= Decimal("0"):
        return target_weights, config.portfolio.max_risk_scale

    scale = target / realized
    scale = max(config.portfolio.min_risk_scale, min(scale, config.portfolio.max_risk_scale))
    return {
        symbol: weight * scale
        for symbol, weight in target_weights.items()
    }, scale


def _portfolio_volatility(
    *,
    candles_by_symbol: dict[str, tuple[Candle, ...]],
    signal_index: int,
    target_weights: dict[str, Decimal],
    window: int,
) -> Decimal:
    start_index = signal_index - window + 1
    if start_index <= 0:
        return Decimal("0")

    returns: list[float] = []
    for index in range(start_index, signal_index + 1):
        portfolio_return = Decimal("0")
        for symbol, weight in target_weights.items():
            if weight == Decimal("0"):
                continue
            candles = candles_by_symbol[symbol]
            asset_return = candles[index].close / candles[index - 1].close - Decimal("1")
            portfolio_return += weight * asset_return
        returns.append(float(portfolio_return))

    if len(returns) < 2:
        return Decimal("0")
    return Decimal(str(pstdev(returns)))


def _relative_strength_target_weights(
    config: BacktestConfig,
    candles_by_symbol: dict[str, tuple[Candle, ...]],
    signal_index: int,
) -> dict[str, Decimal]:
    if config.signal.lookback_window is None:
        raise ValueError("relative_strength_rotation requires lookback_window")

    weights = {symbol: Decimal("0") for symbol in config.trading_pairs}
    ranked: list[tuple[str, Decimal]] = []
    for symbol in config.trading_pairs:
        candles = candles_by_symbol[symbol]
        current_close = candles[signal_index].close
        lookback_close = candles[signal_index - config.signal.lookback_window].close
        momentum = current_close / lookback_close - Decimal("1")
        if momentum >= config.signal.min_momentum:
            ranked.append((symbol, momentum))

    ranked.sort(key=lambda item: item[1], reverse=True)
    active_symbols = [symbol for symbol, _momentum in ranked[: config.signal.top_n]]
    if not active_symbols:
        return weights

    equal_weight = config.portfolio.gross_target / Decimal(len(active_symbols))
    capped_weight = min(equal_weight, config.portfolio.max_symbol_weight)
    for symbol in active_symbols:
        weights[symbol] = capped_weight
    return weights


def _signal_features(
    candles: tuple[Candle, ...],
    *,
    signal_index: int,
    fast_window: int,
    slow_window: int,
    volatility_window: int,
) -> dict[str, Decimal | SignalDirection]:
    closes = tuple(candle.close for candle in candles[: signal_index + 1])
    fast = simple_moving_average(closes, fast_window)
    slow = simple_moving_average(closes, slow_window)
    trend_strength = abs(fast / slow - Decimal("1"))
    volatility_closes = closes[-volatility_window:] if len(closes) >= volatility_window else closes
    volatility = (
        close_to_close_volatility(volatility_closes)
        if len(volatility_closes) >= 3
        else Decimal("0")
    )
    if fast > slow:
        direction = SignalDirection.LONG
    elif fast < slow:
        direction = SignalDirection.SHORT
    else:
        direction = SignalDirection.FLAT
    return {
        "direction": direction,
        "trend_strength": trend_strength,
        "volatility": volatility,
    }


def _direction_can_trade(direction: SignalDirection | Decimal, allow_short: bool) -> bool:
    return direction is SignalDirection.LONG or (allow_short and direction is SignalDirection.SHORT)


def _regime_filter_allows(
    *,
    trend_strength: Decimal | SignalDirection,
    volatility: Decimal | SignalDirection,
    config: BacktestConfig,
) -> bool:
    if not config.regime_filter.enabled:
        return True
    if not isinstance(trend_strength, Decimal) or not isinstance(volatility, Decimal):
        raise ValueError("regime filter features must be decimal values")
    if trend_strength < config.regime_filter.min_trend_strength:
        return False
    if config.regime_filter.max_volatility is not None:
        return volatility <= config.regime_filter.max_volatility
    return True


def _below_rebalance_threshold(
    *,
    delta_notional: Decimal,
    equity: Decimal,
    threshold: Decimal,
) -> bool:
    if equity <= Decimal("0"):
        raise ValueError("equity must be positive")
    if delta_notional == Decimal("0"):
        return True
    return abs(delta_notional) / equity < threshold


def _cap_rebalance_turnover(
    delta_notional_by_symbol: dict[str, Decimal],
    *,
    equity: Decimal,
    max_turnover: Decimal | None,
) -> dict[str, Decimal]:
    if max_turnover is None:
        return delta_notional_by_symbol
    if equity <= Decimal("0"):
        raise ValueError("equity must be positive")

    max_notional = equity * max_turnover
    total_delta = sum((abs(delta) for delta in delta_notional_by_symbol.values()), Decimal("0"))
    if total_delta == Decimal("0") or total_delta <= max_notional:
        return delta_notional_by_symbol

    scale = max_notional / total_delta
    return {
        symbol: delta * scale
        for symbol, delta in delta_notional_by_symbol.items()
    }


def _cap_participation(
    *,
    delta_notional: Decimal,
    execution_price: Decimal,
    candle_volume: Decimal,
    max_participation_rate: Decimal | None,
) -> Decimal:
    if max_participation_rate is None:
        return delta_notional
    if max_participation_rate <= Decimal("0"):
        raise ValueError("max_participation_rate must be positive")
    max_notional = execution_price * candle_volume * max_participation_rate
    if max_notional <= Decimal("0"):
        return Decimal("0")
    if abs(delta_notional) <= max_notional:
        return delta_notional
    sign = Decimal("1") if delta_notional > Decimal("0") else Decimal("-1")
    return sign * max_notional


def _below_min_order_notional(*, delta_notional: Decimal, min_order_notional: Decimal) -> bool:
    if delta_notional == Decimal("0"):
        return True
    return abs(delta_notional) < min_order_notional


def _participation_rate(
    *,
    notional: Decimal,
    execution_price: Decimal,
    candle_volume: Decimal,
) -> Decimal:
    volume_notional = execution_price * candle_volume
    if volume_notional <= Decimal("0"):
        return Decimal("0")
    return notional / volume_notional


def _estimated_capacity_equity(
    *,
    initial_equity: Decimal,
    max_participation_rate: Decimal | None,
    max_observed_participation_rate: Decimal,
) -> Decimal:
    if max_participation_rate is None or max_observed_participation_rate <= Decimal("0"):
        return Decimal("0")
    return initial_equity * max_participation_rate / max_observed_participation_rate


def _drawdown_stop_triggers(
    *,
    equity: Decimal,
    high_watermark: Decimal,
    threshold: Decimal | None,
) -> bool:
    if threshold is None:
        return False
    if high_watermark <= Decimal("0"):
        raise ValueError("high_watermark must be positive")
    drawdown = (high_watermark - equity) / high_watermark
    return drawdown >= threshold


def _validate_candles(config: BacktestConfig, candles_by_symbol: dict[str, tuple[Candle, ...]]) -> None:
    missing = [symbol for symbol in config.trading_pairs if symbol not in candles_by_symbol]
    if missing:
        raise ValueError(f"missing candles for symbols: {', '.join(missing)}")
    if config.signal.signal_type == "moving_average_trend":
        if config.signal.fast_window is None or config.signal.slow_window is None:
            raise ValueError("moving_average_trend requires fast_window and slow_window")
        if config.signal.fast_window <= 0 or config.signal.slow_window <= 0:
            raise ValueError("signal windows must be positive")
        if config.signal.fast_window >= config.signal.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
    elif config.signal.signal_type == "relative_strength_rotation":
        if config.signal.lookback_window is None:
            raise ValueError("relative_strength_rotation requires lookback_window")
        if config.signal.lookback_window <= 0:
            raise ValueError("lookback_window must be positive")
        if config.signal.top_n <= 0:
            raise ValueError("top_n must be positive")
        if config.signal.top_n > len(config.trading_pairs):
            raise ValueError("top_n cannot exceed number of trading pairs")
    else:
        raise ValueError(f"unsupported signal type: {config.signal.signal_type}")
    if config.signal.min_momentum < Decimal("-1"):
        raise ValueError("min_momentum cannot be less than -1")
    if config.regime_filter.min_trend_strength < Decimal("0"):
        raise ValueError("min_trend_strength cannot be negative")
    if (
        config.regime_filter.max_volatility is not None
        and config.regime_filter.max_volatility < Decimal("0")
    ):
        raise ValueError("max_volatility cannot be negative")
    if config.regime_filter.volatility_window is not None and config.regime_filter.volatility_window < 3:
        raise ValueError("volatility_window must be at least 3")
    if config.portfolio.volatility_target is not None and config.portfolio.volatility_target <= Decimal("0"):
        raise ValueError("volatility_target must be positive")
    if config.portfolio.volatility_window is not None and config.portfolio.volatility_window < 3:
        raise ValueError("portfolio volatility_window must be at least 3")
    if config.portfolio.min_risk_scale < Decimal("0"):
        raise ValueError("min_risk_scale cannot be negative")
    if config.portfolio.max_risk_scale <= Decimal("0"):
        raise ValueError("max_risk_scale must be positive")
    if config.portfolio.min_risk_scale > config.portfolio.max_risk_scale:
        raise ValueError("min_risk_scale cannot exceed max_risk_scale")
    if (
        config.portfolio.max_drawdown_stop is not None
        and not Decimal("0") < config.portfolio.max_drawdown_stop < Decimal("1")
    ):
        raise ValueError("max_drawdown_stop must be between 0 and 1")
    if (
        config.portfolio.max_drawdown_stop is not None
        and config.portfolio.drawdown_stop_cooldown_bars <= 0
    ):
        raise ValueError("drawdown_stop_cooldown_bars must be positive when max_drawdown_stop is set")
    if config.portfolio.risk_recovery_bars < 0:
        raise ValueError("risk_recovery_bars cannot be negative")
    if config.portfolio.min_order_notional < Decimal("0"):
        raise ValueError("min_order_notional cannot be negative")
    if (
        config.portfolio.max_participation_rate is not None
        and config.portfolio.max_participation_rate <= Decimal("0")
    ):
        raise ValueError("max_participation_rate must be positive")
    if (
        config.portfolio.max_rebalance_turnover is not None
        and config.portfolio.max_rebalance_turnover <= Decimal("0")
    ):
        raise ValueError("max_rebalance_turnover must be positive")

    reference = candles_by_symbol[config.trading_pairs[0]]
    if len(reference) <= _warmup_window(config):
        raise ValueError("not enough candles for signal warmup window")
    reference_timestamps = tuple(candle.timestamp for candle in reference)

    for symbol in config.trading_pairs:
        candles = candles_by_symbol[symbol]
        if tuple(candle.timestamp for candle in candles) != reference_timestamps:
            raise ValueError("all symbols must share the same timestamp sequence")


def _warmup_window(config: BacktestConfig) -> int:
    risk_windows = []
    if config.portfolio.volatility_window is not None:
        risk_windows.append(config.portfolio.volatility_window + 1)
    if config.signal.signal_type == "moving_average_trend":
        if config.signal.slow_window is None:
            raise ValueError("moving_average_trend requires slow_window")
        risk_windows.append(config.signal.slow_window)
        return max(risk_windows)
    if config.signal.signal_type == "relative_strength_rotation":
        if config.signal.lookback_window is None:
            raise ValueError("relative_strength_rotation requires lookback_window")
        risk_windows.append(config.signal.lookback_window + 1)
        return max(risk_windows)
    raise ValueError(f"unsupported signal type: {config.signal.signal_type}")
