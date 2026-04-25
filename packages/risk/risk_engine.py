"""Account-level pre-trade risk engine."""

from __future__ import annotations

from packages.core.models import AccountSnapshot
from packages.execution.order_intent import OrderIntent
from packages.risk.account_limits import AccountRiskLimits
from packages.risk.kill_switch import KillSwitch
from packages.risk.risk_decision import RiskDecision


class RiskEngine:
    def __init__(self, limits: AccountRiskLimits, kill_switch: KillSwitch | None = None) -> None:
        self._limits = limits
        self._kill_switch = kill_switch or KillSwitch()

    @property
    def kill_switch(self) -> KillSwitch:
        return self._kill_switch

    def evaluate_order_intent(
        self,
        intent: OrderIntent,
        account: AccountSnapshot,
    ) -> RiskDecision:
        if self._kill_switch.active:
            reason = self._kill_switch.reason or "kill switch active"
            return RiskDecision.reject(intent.intent_id, reason)

        order_notional = abs(intent.notional)
        if order_notional > self._limits.max_order_notional:
            return RiskDecision.reject(
                intent.intent_id,
                f"order notional {order_notional} exceeds max {self._limits.max_order_notional}",
            )

        projected_symbol_exposure = account.symbol_exposure(intent.symbol) + order_notional
        if projected_symbol_exposure > self._limits.max_symbol_notional:
            return RiskDecision.reject(
                intent.intent_id,
                "projected symbol exposure exceeds configured limit",
            )

        projected_gross_exposure = account.gross_exposure + order_notional
        if projected_gross_exposure > self._limits.max_gross_notional:
            return RiskDecision.reject(
                intent.intent_id,
                "projected gross exposure exceeds configured limit",
            )

        return RiskDecision.approve(intent.intent_id)
