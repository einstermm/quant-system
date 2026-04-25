"""Funding rate repository interfaces and in-memory implementation."""

from datetime import datetime

from packages.core.models import FundingRate


class InMemoryFundingRateRepository:
    def __init__(self) -> None:
        self._rates: list[FundingRate] = []

    def add_many(self, rates: list[FundingRate] | tuple[FundingRate, ...]) -> None:
        self._rates.extend(rates)
        self._rates.sort(key=lambda rate: rate.timestamp)

    def list(
        self,
        *,
        exchange: str,
        trading_pair: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[FundingRate, ...]:
        return tuple(
            rate
            for rate in self._rates
            if rate.exchange == exchange
            and rate.trading_pair == trading_pair
            and rate.interval == interval
            and (start is None or rate.timestamp >= start)
            and (end is None or rate.timestamp <= end)
        )
