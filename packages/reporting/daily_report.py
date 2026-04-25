"""Daily report builder."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DailyReport:
    account_id: str
    ending_equity: Decimal
    gross_exposure: Decimal
    notes: tuple[str, ...] = ()
