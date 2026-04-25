"""Order book snapshot repository interfaces and in-memory implementation."""

from packages.core.models import OrderBookSnapshot


class InMemoryOrderBookSnapshotRepository:
    def __init__(self) -> None:
        self._snapshots: list[OrderBookSnapshot] = []

    def add_many(self, snapshots: list[OrderBookSnapshot] | tuple[OrderBookSnapshot, ...]) -> None:
        self._snapshots.extend(snapshots)
        self._snapshots.sort(key=lambda snapshot: snapshot.timestamp)

    def latest(self, *, exchange: str, trading_pair: str) -> OrderBookSnapshot | None:
        matches = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.exchange == exchange and snapshot.trading_pair == trading_pair
        ]
        if not matches:
            return None
        return matches[-1]
