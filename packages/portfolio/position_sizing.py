"""Position sizing helpers."""

from decimal import Decimal

from packages.core.models import require_positive


def quantity_from_notional(*, target_notional: Decimal, price: Decimal) -> Decimal:
    require_positive(abs(target_notional), "absolute target_notional")
    require_positive(price, "price")
    return target_notional / price
