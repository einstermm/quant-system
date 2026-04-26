from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.backtesting.config import (
    BacktestConfig,
    PortfolioBacktestConfig,
    SignalBacktestConfig,
)
from packages.core.enums import OrderSide, OrderType, RiskDecisionStatus
from packages.core.models import Candle, OrderRequest
from packages.data.candle_repository import InMemoryCandleRepository
from packages.data.market_data_service import MarketDataService
from packages.execution.order_intent import OrderIntent
from packages.paper_trading.cycle import PaperTradingCycle
from packages.paper_trading.execution_client import PaperExecutionClient
from packages.paper_trading.ledger import PaperLedger
from packages.paper_trading.observation import PaperObservationLoop, load_observations
from packages.risk.account_limits import AccountRiskLimits
from packages.risk.kill_switch import KillSwitch


class PaperTradingTest(TestCase):
    def test_paper_execution_records_fill_and_reconstructs_account(self) -> None:
        with TemporaryDirectory() as directory:
            ledger = PaperLedger(f"{directory}/paper.jsonl")
            client = PaperExecutionClient(ledger, fee_rate=Decimal("0.001"))
            request = OrderRequest(
                client_order_id="order-1",
                strategy_id="unit_strategy",
                symbol="BTC-USDT",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("2"),
            )
            intent = OrderIntent("intent-1", "paper-main", request, Decimal("100"))

            paper_order_id = client.submit_order_intent(intent)
            account = ledger.account_snapshot(
                account_id="paper-main",
                initial_equity=Decimal("1000"),
                mark_prices={"BTC-USDT": Decimal("110")},
            )

            self.assertTrue(paper_order_id.startswith("paper-intent-1-"))
            self.assertEqual(1, len(ledger.records()))
            self.assertEqual(Decimal("799.800"), account.cash)
            self.assertEqual(Decimal("1019.800"), account.equity)
            self.assertEqual(Decimal("220"), account.gross_exposure)

    def test_cycle_generates_risk_approved_paper_order_with_turnover_cap(self) -> None:
        with TemporaryDirectory() as directory:
            repository = InMemoryCandleRepository()
            start = datetime(2025, 1, 1, tzinfo=UTC)
            repository.add_many(
                _candles("BTC-USDT", start, (Decimal("100"), Decimal("110"), Decimal("120")))
            )
            repository.add_many(
                _candles("ETH-USDT", start, (Decimal("100"), Decimal("95"), Decimal("90")))
            )
            ledger = PaperLedger(f"{directory}/paper.jsonl")
            cycle = PaperTradingCycle(
                market_data_service=MarketDataService(repository),
                config=_paper_config(start),
                risk_limits=AccountRiskLimits(
                    max_order_notional=Decimal("1000"),
                    max_symbol_notional=Decimal("2000"),
                    max_gross_notional=Decimal("5000"),
                    max_daily_loss=Decimal("250"),
                    max_drawdown_pct=Decimal("0.10"),
                ),
                ledger=ledger,
                account_id="paper-main",
                initial_equity=Decimal("2000"),
            )

            result = cycle.run_once()

            self.assertEqual("unit_relative_strength", result.strategy_id)
            self.assertEqual(1, len(result.routed_orders))
            self.assertEqual(
                RiskDecisionStatus.APPROVED,
                result.routed_orders[0].risk_decision.status,
            )
            self.assertEqual(1, len(ledger.records()))
            self.assertEqual(Decimal("200.0"), ledger.records()[0].notional)
            self.assertEqual(Decimal("200.0"), result.account.gross_exposure)

    def test_cycle_respects_kill_switch_without_writing_fill(self) -> None:
        with TemporaryDirectory() as directory:
            repository = InMemoryCandleRepository()
            start = datetime(2025, 1, 1, tzinfo=UTC)
            repository.add_many(
                _candles("BTC-USDT", start, (Decimal("100"), Decimal("110"), Decimal("120")))
            )
            repository.add_many(
                _candles("ETH-USDT", start, (Decimal("100"), Decimal("95"), Decimal("90")))
            )
            ledger = PaperLedger(f"{directory}/paper.jsonl")
            cycle = PaperTradingCycle(
                market_data_service=MarketDataService(repository),
                config=_paper_config(start),
                risk_limits=AccountRiskLimits(
                    max_order_notional=Decimal("1000"),
                    max_symbol_notional=Decimal("2000"),
                    max_gross_notional=Decimal("5000"),
                    max_daily_loss=Decimal("250"),
                    max_drawdown_pct=Decimal("0.10"),
                ),
                ledger=ledger,
                account_id="paper-main",
                initial_equity=Decimal("2000"),
                kill_switch=KillSwitch(active=True, reason="manual stop"),
            )

            result = cycle.run_once()

            self.assertEqual(1, len(result.routed_orders))
            self.assertEqual(
                RiskDecisionStatus.REJECTED,
                result.routed_orders[0].risk_decision.status,
            )
            self.assertEqual("manual stop", result.routed_orders[0].risk_decision.reason)
            self.assertEqual(0, len(ledger.records()))
            self.assertEqual(Decimal("2000"), result.account.equity)

    def test_observation_loop_writes_log_summary_and_report(self) -> None:
        with TemporaryDirectory() as directory:
            repository = InMemoryCandleRepository()
            start = datetime(2025, 1, 1, tzinfo=UTC)
            repository.add_many(
                _candles("BTC-USDT", start, (Decimal("100"), Decimal("110"), Decimal("120")))
            )
            repository.add_many(
                _candles("ETH-USDT", start, (Decimal("100"), Decimal("95"), Decimal("90")))
            )
            ledger = PaperLedger(Path(directory) / "paper.jsonl")

            def cycle_factory() -> PaperTradingCycle:
                return PaperTradingCycle(
                    market_data_service=MarketDataService(repository),
                    config=_paper_config(start),
                    risk_limits=AccountRiskLimits(
                        max_order_notional=Decimal("1000"),
                        max_symbol_notional=Decimal("2000"),
                        max_gross_notional=Decimal("5000"),
                        max_daily_loss=Decimal("250"),
                        max_drawdown_pct=Decimal("0.10"),
                    ),
                    ledger=ledger,
                    account_id="paper-main",
                    initial_equity=Decimal("2000"),
                )

            observation_log = Path(directory) / "observation.jsonl"
            summary_json = Path(directory) / "summary.json"
            report_md = Path(directory) / "report.md"
            loop = PaperObservationLoop(
                cycle_factory=cycle_factory,
                observation_log=observation_log,
                summary_json=summary_json,
                report_md=report_md,
                cycles=2,
                interval_seconds=Decimal("0"),
            )

            summary = loop.run()
            records = load_observations(observation_log)

            self.assertEqual("ok", summary.status)
            self.assertEqual(2, summary.cycles)
            self.assertEqual(2, summary.ok_cycles)
            self.assertEqual(2, summary.approved_orders)
            self.assertEqual(2, len(records))
            self.assertIsNone(records[0]["pre_cycle"])
            self.assertTrue(summary_json.exists())
            self.assertIn("Paper Observation Report", report_md.read_text(encoding="utf-8"))

    def test_observation_loop_records_pre_cycle_payload(self) -> None:
        with TemporaryDirectory() as directory:
            repository = InMemoryCandleRepository()
            start = datetime(2025, 1, 1, tzinfo=UTC)
            repository.add_many(
                _candles("BTC-USDT", start, (Decimal("100"), Decimal("110"), Decimal("120")))
            )
            repository.add_many(
                _candles("ETH-USDT", start, (Decimal("100"), Decimal("95"), Decimal("90")))
            )
            ledger = PaperLedger(Path(directory) / "paper.jsonl")

            def cycle_factory() -> PaperTradingCycle:
                return PaperTradingCycle(
                    market_data_service=MarketDataService(repository),
                    config=_paper_config(start),
                    risk_limits=AccountRiskLimits(
                        max_order_notional=Decimal("1000"),
                        max_symbol_notional=Decimal("2000"),
                        max_gross_notional=Decimal("5000"),
                        max_daily_loss=Decimal("250"),
                        max_drawdown_pct=Decimal("0.10"),
                    ),
                    ledger=ledger,
                    account_id="paper-main",
                    initial_equity=Decimal("2000"),
                )

            observation_log = Path(directory) / "observation.jsonl"
            loop = PaperObservationLoop(
                cycle_factory=cycle_factory,
                observation_log=observation_log,
                summary_json=Path(directory) / "summary.json",
                report_md=Path(directory) / "report.md",
                cycles=1,
                interval_seconds=Decimal("0"),
                pre_cycle_hook=lambda: {"market_data_refresh": [{"status": "ok"}]},
            )

            loop.run()
            records = load_observations(observation_log)

            self.assertEqual({"market_data_refresh": [{"status": "ok"}]}, records[0]["pre_cycle"])


def _paper_config(start: datetime) -> BacktestConfig:
    return BacktestConfig(
        strategy_id="unit_relative_strength",
        exchange="binance",
        market_type="spot",
        trading_pairs=("BTC-USDT", "ETH-USDT"),
        interval="4h",
        start=start,
        end=start + timedelta(hours=12),
        initial_equity=Decimal("2000"),
        fee_rate=Decimal("0"),
        slippage_bps=Decimal("0"),
        signal=SignalBacktestConfig(
            signal_type="relative_strength_rotation",
            lookback_window=1,
            top_n=1,
            min_momentum=Decimal("0"),
        ),
        portfolio=PortfolioBacktestConfig(
            gross_target=Decimal("0.50"),
            max_symbol_weight=Decimal("0.25"),
            rebalance_threshold=Decimal("0.01"),
            min_order_notional=Decimal("10"),
            max_participation_rate=Decimal("0.02"),
            max_rebalance_turnover=Decimal("0.10"),
        ),
    )


def _candles(
    symbol: str,
    start: datetime,
    closes: tuple[Decimal, ...],
) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            exchange="binance",
            trading_pair=symbol,
            interval="4h",
            timestamp=start + timedelta(hours=4 * index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=Decimal("100000"),
        )
        for index, close in enumerate(closes)
    )
