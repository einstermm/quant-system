"""Event contracts shared between services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from packages.core.enums import RiskDecisionStatus
from packages.core.models import OrderState, Signal, utc_now


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class SignalGenerated(DomainEvent):
    signal: Signal | None = None


@dataclass(frozen=True, slots=True)
class RiskDecisionMade(DomainEvent):
    intent_id: str = ""
    status: RiskDecisionStatus = RiskDecisionStatus.REJECTED
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionReportReceived(DomainEvent):
    order_state: OrderState | None = None
