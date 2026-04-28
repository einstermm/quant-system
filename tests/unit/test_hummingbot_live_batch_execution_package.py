from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.live_batch_execution_package import (
    build_live_batch_execution_package,
)
from packages.core.models import Candle
from packages.data.sqlite_candle_repository import SQLiteCandleRepository


class HummingbotLiveBatchExecutionPackageTest(TestCase):
    def test_generates_candidate_orders_pending_exchange_state_check(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategy_dir = _strategy_dir(root)
            db_path = root / "candles.sqlite"
            _seed_candles(db_path)

            package = build_live_batch_execution_package(
                activation_plan=_activation_plan(),
                market_data_refresh=_refresh(),
                live_risk_config=_risk_config(),
                strategy_dir=strategy_dir,
                db_path=db_path,
                output_dir=root / "package",
                session_id="unit",
                allowed_pairs=("BTC-USDT", "ETH-USDT"),
            )

            self.assertEqual(
                "live_batch_execution_package_ready_pending_exchange_state_check",
                package.decision,
            )
            self.assertEqual(2, len(package.candidate_orders))
            self.assertFalse(package.to_dict()["execution_runner_generated"])
            self.assertFalse(package.to_dict()["live_order_submission_armed"])

    def test_blocks_without_approved_activation_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategy_dir = _strategy_dir(root)
            db_path = root / "candles.sqlite"
            _seed_candles(db_path)

            package = build_live_batch_execution_package(
                activation_plan={**_activation_plan(), "decision": "pending"},
                market_data_refresh=_refresh(),
                live_risk_config=_risk_config(),
                strategy_dir=strategy_dir,
                db_path=db_path,
                output_dir=root / "package",
                session_id="unit",
                allowed_pairs=("BTC-USDT", "ETH-USDT"),
            )

            self.assertEqual("live_batch_execution_package_blocked", package.decision)


def _strategy_dir(root: Path) -> Path:
    strategy_dir = root / "strategy"
    strategy_dir.mkdir()
    (strategy_dir / "config.yml").write_text(
        "strategy_id: crypto_relative_strength_v1\n"
        "universe:\n"
        "  exchange: binance\n"
        "  market_type: spot\n"
        "  quote_asset: USDT\n"
        "  symbols:\n"
        "    - BTC-USDT\n"
        "    - ETH-USDT\n"
        "timeframe: 4h\n"
        "signal:\n"
        "  type: relative_strength_rotation\n"
        "  lookback_window: 3\n"
        "  top_n: 2\n"
        "  min_momentum: \"0\"\n",
        encoding="utf-8",
    )
    (strategy_dir / "portfolio.yml").write_text(
        "gross_target: \"0.50\"\n"
        "max_symbol_weight: \"0.25\"\n"
        "rebalance_threshold: \"0.05\"\n"
        "min_order_notional: \"10\"\n",
        encoding="utf-8",
    )
    (strategy_dir / "backtest.yml").write_text(
        "start: \"2026-01-01\"\n"
        "end: \"2026-01-10\"\n"
        "initial_equity: \"10000\"\n"
        "fee_rate: \"0.001\"\n"
        "slippage_bps: \"5\"\n",
        encoding="utf-8",
    )
    return strategy_dir


def _seed_candles(db_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with SQLiteCandleRepository(db_path) as repository:
        candles = []
        for pair, base_price in (("BTC-USDT", 100), ("ETH-USDT", 50)):
            for index in range(4):
                price = base_price + (index * 5)
                candles.append(
                    Candle(
                        exchange="binance",
                        trading_pair=pair,
                        interval="4h",
                        timestamp=start + timedelta(hours=4 * index),
                        open=price,
                        high=price + 1,
                        low=price - 1,
                        close=price,
                        volume=1000,
                    )
                )
        repository.add_many(candles)


def _activation_plan() -> dict[str, object]:
    return {
        "decision": "live_batch_activation_plan_approved",
        "strategy_id": "crypto_relative_strength_v1",
        "batch_id": "batch-1",
        "connector": "binance",
        "batch_scope": {
            "max_orders": 2,
            "max_total_notional": "500",
        },
    }


def _refresh() -> list[dict[str, object]]:
    return [
        {"trading_pair": "BTC-USDT", "status": "ok"},
        {"trading_pair": "ETH-USDT", "status": "ok"},
    ]


def _risk_config() -> dict[str, object]:
    return {
        "max_order_notional": "250",
        "max_symbol_notional": "500",
        "max_gross_notional": "1000",
        "max_daily_loss": "50",
        "max_drawdown_pct": "0.05",
    }
