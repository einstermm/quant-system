"""Tax export placeholders."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TaxLotRow:
    trade_date: date
    symbol: str
    quantity: Decimal
    proceeds_cad: Decimal
    cost_basis_cad: Decimal
    fees_cad: Decimal
