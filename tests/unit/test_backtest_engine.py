import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from packages.backtesting.config import (
    BacktestConfig,
    PortfolioBacktestConfig,
    RegimeFilterBacktestConfig,
    SignalBacktestConfig,
    load_backtest_config,
)
from packages.backtesting.engine import BacktestEngine
from packages.core.models import Candle
from packages.data.candle_repository import InMemoryCandleRepository
from packages.data.market_data_service import MarketDataService


class BacktestEngineTest(TestCase):
    def test_loads_crypto_momentum_config(self) -> None:
        config = load_backtest_config(
            Path(__file__).parents[2] / "strategies" / "crypto_momentum_v1"
        )

        self.assertEqual("crypto_momentum_v1", config.strategy_id)
        self.assertEqual(("BTC-USDT", "ETH-USDT"), config.trading_pairs)
        self.assertEqual("4h", config.interval)
        self.assertEqual(datetime(2025, 1, 1, tzinfo=UTC), config.start)
        self.assertEqual(datetime(2026, 1, 1, tzinfo=UTC), config.end)
        self.assertEqual(Decimal("10000"), config.initial_equity)
        self.assertFalse(config.regime_filter.enabled)

    def test_loads_crypto_relative_strength_config(self) -> None:
        config = load_backtest_config(
            Path(__file__).parents[2] / "strategies" / "crypto_relative_strength_v1"
        )

        self.assertEqual("crypto_relative_strength_v1", config.strategy_id)
        self.assertEqual("relative_strength_rotation", config.signal.signal_type)
        self.assertEqual(
            ("BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT", "XRP-USDT", "ADA-USDT"),
            config.trading_pairs,
        )
        self.assertEqual(72, config.signal.lookback_window)
        self.assertEqual(2, config.signal.top_n)
        self.assertEqual(Decimal("0"), config.signal.min_momentum)
        self.assertEqual(Decimal("0.25"), config.portfolio.max_symbol_weight)
        self.assertEqual(Decimal("0.010"), config.portfolio.volatility_target)
        self.assertEqual(72, config.portfolio.volatility_window)
        self.assertEqual(Decimal("0.10"), config.portfolio.max_drawdown_stop)
        self.assertEqual(36, config.portfolio.drawdown_stop_cooldown_bars)
        self.assertFalse(config.portfolio.reset_drawdown_high_watermark_on_stop)
        self.assertEqual(18, config.portfolio.risk_recovery_bars)
        self.assertEqual(Decimal("10"), config.portfolio.min_order_notional)
        self.assertEqual(Decimal("0.02"), config.portfolio.max_participation_rate)
        self.assertEqual(Decimal("0.25"), config.portfolio.max_rebalance_turnover)

    def test_runs_spot_momentum_backtest_without_hummingbot(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = _sample_candles(start)
        repository = InMemoryCandleRepository()
        repository.add_many(candles["BTC-USDT"] + candles["ETH-USDT"])
        service = MarketDataService(repository)
        config = BacktestConfig(
            strategy_id="unit_momentum",
            exchange="binance",
            market_type="spot",
            trading_pairs=("BTC-USDT", "ETH-USDT"),
            interval="1h",
            start=start,
            end=start + timedelta(hours=6),
            initial_equity=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            signal=SignalBacktestConfig(
                signal_type="moving_average_trend",
                fast_window=2,
                slow_window=3,
            ),
            portfolio=PortfolioBacktestConfig(
                gross_target=Decimal("0.50"),
                max_symbol_weight=Decimal("0.25"),
                rebalance_threshold=Decimal("0"),
            ),
        )

        result = BacktestEngine(service, code_version="unit").run(config)
        payload = result.to_dict()

        self.assertEqual("unit_momentum", result.strategy_id)
        self.assertGreater(result.metrics["end_equity"], Decimal("1000"))
        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(result.metrics["turnover"], Decimal("0"))
        self.assertIn("tail_loss", result.metrics)
        self.assertEqual("unit", result.code_version)
        self.assertEqual("unit_momentum", payload["strategy_id"])
        json.dumps(payload)

    def test_regime_filter_can_block_trades(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = _sample_candles(start)
        repository = InMemoryCandleRepository()
        repository.add_many(candles["BTC-USDT"] + candles["ETH-USDT"])
        service = MarketDataService(repository)
        config = BacktestConfig(
            strategy_id="unit_momentum",
            exchange="binance",
            market_type="spot",
            trading_pairs=("BTC-USDT", "ETH-USDT"),
            interval="1h",
            start=start,
            end=start + timedelta(hours=6),
            initial_equity=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            signal=SignalBacktestConfig(
                signal_type="moving_average_trend",
                fast_window=2,
                slow_window=3,
            ),
            portfolio=PortfolioBacktestConfig(
                gross_target=Decimal("0.50"),
                max_symbol_weight=Decimal("0.25"),
                rebalance_threshold=Decimal("0"),
            ),
            regime_filter=RegimeFilterBacktestConfig(
                enabled=True,
                min_trend_strength=Decimal("10"),
            ),
        )

        result = BacktestEngine(service, code_version="unit").run(config)

        self.assertEqual(0, result.metrics["trade_count"])
        self.assertEqual(Decimal("1000"), result.metrics["end_equity"])

    def test_runs_relative_strength_rotation_backtest(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = _sample_candles(start)
        repository = InMemoryCandleRepository()
        repository.add_many(candles["BTC-USDT"] + candles["ETH-USDT"])
        service = MarketDataService(repository)
        config = BacktestConfig(
            strategy_id="unit_relative_strength",
            exchange="binance",
            market_type="spot",
            trading_pairs=("BTC-USDT", "ETH-USDT"),
            interval="1h",
            start=start,
            end=start + timedelta(hours=6),
            initial_equity=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            signal=SignalBacktestConfig(
                signal_type="relative_strength_rotation",
                lookback_window=2,
                top_n=1,
                min_momentum=Decimal("0"),
            ),
            portfolio=PortfolioBacktestConfig(
                gross_target=Decimal("0.50"),
                max_symbol_weight=Decimal("0.50"),
                rebalance_threshold=Decimal("0"),
            ),
        )

        result = BacktestEngine(service, code_version="unit").run(config)

        self.assertEqual("unit_relative_strength", result.strategy_id)
        self.assertGreater(result.metrics["trade_count"], 0)
        self.assertGreater(result.metrics["end_equity"], Decimal("1000"))

    def test_volatility_target_can_scale_exposure_down(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = _volatile_candles(start)
        repository = InMemoryCandleRepository()
        repository.add_many(candles["BTC-USDT"] + candles["ETH-USDT"])
        service = MarketDataService(repository)
        config = BacktestConfig(
            strategy_id="unit_relative_strength",
            exchange="binance",
            market_type="spot",
            trading_pairs=("BTC-USDT", "ETH-USDT"),
            interval="1h",
            start=start,
            end=start + timedelta(hours=7),
            initial_equity=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            signal=SignalBacktestConfig(
                signal_type="relative_strength_rotation",
                lookback_window=2,
                top_n=1,
                min_momentum=Decimal("-1"),
            ),
            portfolio=PortfolioBacktestConfig(
                gross_target=Decimal("0.50"),
                max_symbol_weight=Decimal("0.50"),
                rebalance_threshold=Decimal("0"),
                volatility_target=Decimal("0.0001"),
                volatility_window=3,
                max_risk_scale=Decimal("1"),
            ),
        )

        result = BacktestEngine(service, code_version="unit").run(config)

        self.assertLess(result.metrics["average_risk_scale"], Decimal("1"))
        self.assertGreater(result.metrics["trade_count"], 0)

    def test_rebalance_turnover_cap_limits_trade_size(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = _sample_candles(start)
        repository = InMemoryCandleRepository()
        repository.add_many(candles["BTC-USDT"] + candles["ETH-USDT"])
        service = MarketDataService(repository)
        config = BacktestConfig(
            strategy_id="unit_relative_strength",
            exchange="binance",
            market_type="spot",
            trading_pairs=("BTC-USDT", "ETH-USDT"),
            interval="1h",
            start=start,
            end=start + timedelta(hours=6),
            initial_equity=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            signal=SignalBacktestConfig(
                signal_type="relative_strength_rotation",
                lookback_window=2,
                top_n=1,
                min_momentum=Decimal("0"),
            ),
            portfolio=PortfolioBacktestConfig(
                gross_target=Decimal("0.50"),
                max_symbol_weight=Decimal("0.50"),
                rebalance_threshold=Decimal("0"),
                max_rebalance_turnover=Decimal("0.10"),
            ),
        )

        result = BacktestEngine(service, code_version="unit").run(config)

        self.assertGreater(result.trades, ())
        self.assertLessEqual(result.trades[0].notional, Decimal("100.0000000000000000000000001"))

    def test_min_order_notional_skips_small_trades(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = _sample_candles(start)
        repository = InMemoryCandleRepository()
        repository.add_many(candles["BTC-USDT"] + candles["ETH-USDT"])
        service = MarketDataService(repository)
        config = BacktestConfig(
            strategy_id="unit_relative_strength",
            exchange="binance",
            market_type="spot",
            trading_pairs=("BTC-USDT", "ETH-USDT"),
            interval="1h",
            start=start,
            end=start + timedelta(hours=6),
            initial_equity=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            signal=SignalBacktestConfig(
                signal_type="relative_strength_rotation",
                lookback_window=2,
                top_n=1,
                min_momentum=Decimal("0"),
            ),
            portfolio=PortfolioBacktestConfig(
                gross_target=Decimal("0.50"),
                max_symbol_weight=Decimal("0.50"),
                rebalance_threshold=Decimal("0"),
                min_order_notional=Decimal("10000"),
            ),
        )

        result = BacktestEngine(service, code_version="unit").run(config)

        self.assertEqual(0, result.metrics["trade_count"])
        self.assertGreater(result.metrics["min_order_skipped_count"], 0)

    def test_participation_cap_limits_trade_size(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=UTC)
        candles = _sample_candles(start)
        repository = InMemoryCandleRepository()
        repository.add_many(candles["BTC-USDT"] + candles["ETH-USDT"])
        service = MarketDataService(repository)
        config = BacktestConfig(
            strategy_id="unit_relative_strength",
            exchange="binance",
            market_type="spot",
            trading_pairs=("BTC-USDT", "ETH-USDT"),
            interval="1h",
            start=start,
            end=start + timedelta(hours=6),
            initial_equity=Decimal("1000"),
            fee_rate=Decimal("0"),
            slippage_bps=Decimal("0"),
            signal=SignalBacktestConfig(
                signal_type="relative_strength_rotation",
                lookback_window=2,
                top_n=1,
                min_momentum=Decimal("0"),
            ),
            portfolio=PortfolioBacktestConfig(
                gross_target=Decimal("0.50"),
                max_symbol_weight=Decimal("0.50"),
                rebalance_threshold=Decimal("0"),
                max_participation_rate=Decimal("0.01"),
            ),
        )

        result = BacktestEngine(service, code_version="unit").run(config)

        self.assertGreater(result.metrics["participation_capped_count"], 0)
        self.assertLessEqual(
            result.metrics["max_observed_participation_rate"],
            Decimal("0.0100000000000000000000000001"),
        )


def _sample_candles(start: datetime) -> dict[str, tuple[Candle, ...]]:
    btc = []
    eth = []
    for index in range(6):
        timestamp = start + timedelta(hours=index)
        btc_open = Decimal("100") + Decimal(index)
        eth_open = Decimal("200") - Decimal(index)
        btc.append(
            Candle(
                exchange="binance",
                trading_pair="BTC-USDT",
                interval="1h",
                timestamp=timestamp,
                open=btc_open,
                high=btc_open + Decimal("2"),
                low=btc_open - Decimal("1"),
                close=btc_open + Decimal("1"),
                volume=Decimal("10"),
            )
        )
        eth.append(
            Candle(
                exchange="binance",
                trading_pair="ETH-USDT",
                interval="1h",
                timestamp=timestamp,
                open=eth_open,
                high=eth_open + Decimal("1"),
                low=eth_open - Decimal("2"),
                close=eth_open - Decimal("1"),
                volume=Decimal("10"),
            )
        )
    return {"BTC-USDT": tuple(btc), "ETH-USDT": tuple(eth)}


def _volatile_candles(start: datetime) -> dict[str, tuple[Candle, ...]]:
    btc = []
    eth = []
    btc_prices = (Decimal("100"), Decimal("110"), Decimal("95"), Decimal("115"), Decimal("90"), Decimal("120"), Decimal("94"), Decimal("125"))
    eth_prices = (Decimal("200"), Decimal("198"), Decimal("201"), Decimal("199"), Decimal("202"), Decimal("200"), Decimal("203"), Decimal("201"))
    for index, (btc_price, eth_price) in enumerate(zip(btc_prices, eth_prices, strict=True)):
        timestamp = start + timedelta(hours=index)
        btc.append(
            Candle(
                exchange="binance",
                trading_pair="BTC-USDT",
                interval="1h",
                timestamp=timestamp,
                open=btc_price,
                high=btc_price + Decimal("2"),
                low=btc_price - Decimal("2"),
                close=btc_price,
                volume=Decimal("10"),
            )
        )
        eth.append(
            Candle(
                exchange="binance",
                trading_pair="ETH-USDT",
                interval="1h",
                timestamp=timestamp,
                open=eth_price,
                high=eth_price + Decimal("2"),
                low=eth_price - Decimal("2"),
                close=eth_price,
                volume=Decimal("10"),
            )
        )
    return {"BTC-USDT": tuple(btc), "ETH-USDT": tuple(eth)}
