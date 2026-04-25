"""In-memory metrics placeholder."""

from decimal import Decimal


class GaugeRegistry:
    def __init__(self) -> None:
        self._gauges: dict[str, Decimal] = {}

    def set(self, name: str, value: Decimal) -> None:
        self._gauges[name] = value

    def get(self, name: str) -> Decimal | None:
        return self._gauges.get(name)
