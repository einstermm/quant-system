"""Risk decision result types."""

from dataclasses import dataclass

from packages.core.enums import RiskDecisionStatus


@dataclass(frozen=True, slots=True)
class RiskDecision:
    status: RiskDecisionStatus
    reason: str
    intent_id: str

    @property
    def approved(self) -> bool:
        return self.status is RiskDecisionStatus.APPROVED

    @classmethod
    def approve(cls, intent_id: str) -> "RiskDecision":
        return cls(RiskDecisionStatus.APPROVED, "approved", intent_id)

    @classmethod
    def reject(cls, intent_id: str, reason: str) -> "RiskDecision":
        return cls(RiskDecisionStatus.REJECTED, reason, intent_id)

    @classmethod
    def reduce_only(cls, intent_id: str, reason: str) -> "RiskDecision":
        return cls(RiskDecisionStatus.REDUCE_ONLY, reason, intent_id)
