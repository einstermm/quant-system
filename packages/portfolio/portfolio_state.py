"""Portfolio state wrapper."""

from dataclasses import dataclass

from packages.core.models import AccountSnapshot


@dataclass(frozen=True, slots=True)
class PortfolioState:
    account: AccountSnapshot

    @property
    def gross_exposure_ratio(self) -> float:
        return float(self.account.gross_exposure / self.account.equity)
