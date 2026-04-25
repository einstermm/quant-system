"""Position accounting placeholders."""

from decimal import Decimal


class PositionLedger:
    def __init__(self) -> None:
        self._quantities: dict[str, Decimal] = {}

    def apply_fill(self, *, symbol: str, signed_quantity: Decimal) -> None:
        self._quantities[symbol] = self._quantities.get(symbol, Decimal("0")) + signed_quantity

    def quantity(self, symbol: str) -> Decimal:
        return self._quantities.get(symbol, Decimal("0"))
