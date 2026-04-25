"""Risk limit configuration."""

from dataclasses import dataclass
from decimal import Decimal

from packages.core.models import require_positive


@dataclass(frozen=True, slots=True)
class AccountRiskLimits:
    max_order_notional: Decimal
    max_symbol_notional: Decimal
    max_gross_notional: Decimal
    max_daily_loss: Decimal
    max_drawdown_pct: Decimal

    def __post_init__(self) -> None:
        require_positive(self.max_order_notional, "max_order_notional")
        require_positive(self.max_symbol_notional, "max_symbol_notional")
        require_positive(self.max_gross_notional, "max_gross_notional")
        require_positive(self.max_daily_loss, "max_daily_loss")
        if not Decimal("0") < self.max_drawdown_pct < Decimal("1"):
            raise ValueError("max_drawdown_pct must be between 0 and 1")
