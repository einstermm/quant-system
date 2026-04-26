"""Single-cycle local paper trading runner."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from packages.backtesting.config import BacktestConfig
from packages.backtesting.result import decimal_to_str
from packages.core.enums import OrderSide
from packages.core.models import AccountSnapshot, Candle, OrderRequest
from packages.core.enums import OrderType
from packages.data.market_data_service import CandleQueryResult, MarketDataService
from packages.execution.order_intent import OrderIntent
from packages.execution.order_router import OrderRouter, RoutedOrder
from packages.paper_trading.ledger import PaperLedger
from packages.risk.account_limits import AccountRiskLimits
from packages.risk.kill_switch import KillSwitch
from packages.risk.risk_engine import RiskEngine
from packages.paper_trading.execution_client import PaperExecutionClient


@dataclass(frozen=True, slots=True)
class PaperCycleResult:
    strategy_id: str
    account: AccountSnapshot
    target_weights: dict[str, Decimal]
    routed_orders: tuple[RoutedOrder, ...]
    ledger_path: str
    market_data: dict[str, dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "account": {
                "account_id": self.account.account_id,
                "equity": decimal_to_str(self.account.equity),
                "cash": decimal_to_str(self.account.cash),
                "gross_exposure": decimal_to_str(self.account.gross_exposure),
                "positions": [
                    {
                        "symbol": position.symbol,
                        "quantity": decimal_to_str(position.quantity),
                        "mark_price": decimal_to_str(position.mark_price),
                        "notional": decimal_to_str(position.notional),
                    }
                    for position in self.account.positions
                ],
            },
            "target_weights": {
                symbol: decimal_to_str(weight)
                for symbol, weight in self.target_weights.items()
            },
            "routed_orders": [
                {
                    "intent_id": routed.intent_id,
                    "risk_status": routed.risk_decision.status.value,
                    "risk_reason": routed.risk_decision.reason,
                    "external_order_id": routed.external_order_id,
                }
                for routed in self.routed_orders
            ],
            "ledger_path": self.ledger_path,
            "market_data": self.market_data,
        }


class PaperTradingCycle:
    def __init__(
        self,
        *,
        market_data_service: MarketDataService,
        config: BacktestConfig,
        risk_limits: AccountRiskLimits,
        ledger: PaperLedger,
        account_id: str,
        initial_equity: Decimal,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self._market_data_service = market_data_service
        self._config = config
        self._risk_limits = risk_limits
        self._ledger = ledger
        self._account_id = account_id
        self._initial_equity = initial_equity
        self._kill_switch = kill_switch or KillSwitch()

    def run_once(self) -> PaperCycleResult:
        query_results = self._market_data_service.load_many(self._config.candle_queries())
        _assert_market_data_ready(tuple(query_results.values()))
        candles_by_symbol = {
            result.query.trading_pair: result.candles
            for result in query_results.values()
        }
        latest_prices = {
            symbol: candles[-1].close
            for symbol, candles in candles_by_symbol.items()
        }
        latest_volumes = {
            symbol: candles[-1].volume
            for symbol, candles in candles_by_symbol.items()
        }
        account = self._ledger.account_snapshot(
            account_id=self._account_id,
            initial_equity=self._initial_equity,
            mark_prices=latest_prices,
        )
        target_weights = _relative_strength_target_weights(self._config, candles_by_symbol)
        intents = _build_intents(
            config=self._config,
            account=account,
            account_id=self._account_id,
            target_weights=target_weights,
            latest_prices=latest_prices,
            latest_volumes=latest_volumes,
        )
        execution_client = PaperExecutionClient(self._ledger, fee_rate=self._config.fee_rate)
        router = OrderRouter(RiskEngine(self._risk_limits, self._kill_switch), execution_client)
        routed_orders = tuple(router.submit(intent, account) for intent in intents)
        final_account = self._ledger.account_snapshot(
            account_id=self._account_id,
            initial_equity=self._initial_equity,
            mark_prices=latest_prices,
        )
        return PaperCycleResult(
            strategy_id=self._config.strategy_id,
            account=final_account,
            target_weights=target_weights,
            routed_orders=routed_orders,
            ledger_path=str(self._ledger.path),
            market_data={
                result.query.key: result.summary()
                for result in query_results.values()
            },
        )


def _relative_strength_target_weights(
    config: BacktestConfig,
    candles_by_symbol: dict[str, tuple[Candle, ...]],
) -> dict[str, Decimal]:
    if config.signal.signal_type != "relative_strength_rotation":
        raise ValueError("paper cycle currently supports relative_strength_rotation")
    if config.signal.lookback_window is None:
        raise ValueError("relative_strength_rotation requires lookback_window")

    ranked: list[tuple[str, Decimal]] = []
    for symbol in config.trading_pairs:
        candles = candles_by_symbol[symbol]
        if len(candles) <= config.signal.lookback_window:
            raise ValueError(f"not enough candles for {symbol} lookback window")
        current_close = candles[-1].close
        lookback_close = candles[-1 - config.signal.lookback_window].close
        momentum = current_close / lookback_close - Decimal("1")
        if momentum >= config.signal.min_momentum:
            ranked.append((symbol, momentum))

    ranked.sort(key=lambda item: item[1], reverse=True)
    active_symbols = [symbol for symbol, _momentum in ranked[: config.signal.top_n]]
    weights = {symbol: Decimal("0") for symbol in config.trading_pairs}
    if not active_symbols:
        return weights

    equal_weight = config.portfolio.gross_target / Decimal(len(active_symbols))
    capped_weight = min(equal_weight, config.portfolio.max_symbol_weight)
    for symbol in active_symbols:
        weights[symbol] = capped_weight
    return weights


def _build_intents(
    *,
    config: BacktestConfig,
    account: AccountSnapshot,
    account_id: str,
    target_weights: dict[str, Decimal],
    latest_prices: dict[str, Decimal],
    latest_volumes: dict[str, Decimal],
) -> tuple[OrderIntent, ...]:
    delta_notional_by_symbol: dict[str, Decimal] = {}
    current_notional_by_symbol: dict[str, Decimal] = {}
    for symbol, target_weight in target_weights.items():
        target_notional = account.equity * target_weight
        current_notional = _current_symbol_notional(account, symbol)
        current_notional_by_symbol[symbol] = current_notional
        delta_notional = target_notional - current_notional
        if _below_threshold(delta_notional, account.equity, config.portfolio.rebalance_threshold):
            delta_notional = Decimal("0")
        delta_notional_by_symbol[symbol] = delta_notional

    delta_notional_by_symbol = _cap_rebalance_turnover(
        delta_notional_by_symbol,
        equity=account.equity,
        max_turnover=config.portfolio.max_rebalance_turnover,
    )

    intents: list[OrderIntent] = []
    for symbol, delta_notional in delta_notional_by_symbol.items():
        price = latest_prices[symbol]
        current_notional = current_notional_by_symbol[symbol]
        delta_notional = _cap_participation(
            delta_notional=delta_notional,
            execution_price=price,
            candle_volume=latest_volumes[symbol],
            max_participation_rate=config.portfolio.max_participation_rate,
        )
        if abs(delta_notional) < config.portfolio.min_order_notional:
            continue

        side = OrderSide.BUY if delta_notional > 0 else OrderSide.SELL
        quantity = abs(delta_notional) / price
        reduce_only = side is OrderSide.SELL and current_notional > 0
        intent_id = f"{config.strategy_id}-{symbol}-{len(intents) + 1}"
        request = OrderRequest(
            client_order_id=intent_id,
            strategy_id=config.strategy_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            reduce_only=reduce_only,
        )
        intents.append(OrderIntent(intent_id, account_id, request, price))
    return tuple(intents)


def _current_symbol_notional(account: AccountSnapshot, symbol: str) -> Decimal:
    return sum(
        (position.notional for position in account.positions if position.symbol == symbol),
        Decimal("0"),
    )


def _below_threshold(delta_notional: Decimal, equity: Decimal, threshold: Decimal) -> bool:
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


def _assert_market_data_ready(query_results: tuple[CandleQueryResult, ...]) -> None:
    for result in query_results:
        if not result.candles:
            raise ValueError(f"no candles loaded for {result.query.trading_pair}")
        if not result.complete:
            raise ValueError(f"incomplete candle data for {result.query.key}")
