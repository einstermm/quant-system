from datetime import UTC, datetime
from decimal import Decimal
from unittest import TestCase

from packages.core.models import FundingRate, OrderBookLevel, OrderBookSnapshot
from packages.data.funding_rate_repository import InMemoryFundingRateRepository
from packages.data.order_book_repository import InMemoryOrderBookSnapshotRepository


class MarketDataModelsTest(TestCase):
    def test_funding_rates_are_queryable(self) -> None:
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        repository = InMemoryFundingRateRepository()
        repository.add_many(
            (
                FundingRate("binance", "BTC-USDT", "8h", timestamp, Decimal("0.0001")),
            )
        )

        rates = repository.list(exchange="binance", trading_pair="BTC-USDT", interval="8h")

        self.assertEqual(1, len(rates))
        self.assertEqual(Decimal("0.0001"), rates[0].rate)

    def test_order_book_snapshot_validates_sorting_and_spread(self) -> None:
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        snapshot = OrderBookSnapshot(
            exchange="binance",
            trading_pair="BTC-USDT",
            timestamp=timestamp,
            bids=(
                OrderBookLevel(Decimal("99"), Decimal("1.2")),
                OrderBookLevel(Decimal("98"), Decimal("2.0")),
            ),
            asks=(
                OrderBookLevel(Decimal("100"), Decimal("1.1")),
                OrderBookLevel(Decimal("101"), Decimal("2.3")),
            ),
        )
        repository = InMemoryOrderBookSnapshotRepository()
        repository.add_many((snapshot,))

        self.assertEqual(snapshot, repository.latest(exchange="binance", trading_pair="BTC-USDT"))

        with self.assertRaises(ValueError):
            OrderBookSnapshot(
                exchange="binance",
                trading_pair="BTC-USDT",
                timestamp=timestamp,
                bids=(OrderBookLevel(Decimal("101"), Decimal("1")),),
                asks=(OrderBookLevel(Decimal("100"), Decimal("1")),),
            )
