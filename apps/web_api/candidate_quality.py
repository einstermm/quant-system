"""Research-stage quality checks for candidate backtests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CandidateGateDefinition:
    gate_id: str
    label: str
    metric_key: str
    operator: str
    threshold: Decimal
    unit: str


CANDIDATE_GATE_DEFINITIONS = (
    CandidateGateDefinition("total_return_positive", "总收益非负", "total_return", ">=", Decimal("0"), "percent"),
    CandidateGateDefinition("max_drawdown_limit", "最大回撤不超过 20%", "max_drawdown", "<=", Decimal("0.20"), "percent"),
    CandidateGateDefinition("tail_loss_limit", "尾部亏损不超过 8%", "tail_loss", "<=", Decimal("0.08"), "percent"),
    CandidateGateDefinition("turnover_limit", "换手不超过 45", "turnover", "<=", Decimal("45"), "number"),
    CandidateGateDefinition("trade_count_minimum", "至少 1 笔成交", "trade_count", ">=", Decimal("1"), "number"),
)


def evaluate_candidate_quality(metrics: Mapping[str, object]) -> dict[str, object]:
    gates = [_evaluate_gate(definition, metrics) for definition in CANDIDATE_GATE_DEFINITIONS]
    failed = [gate for gate in gates if gate["status"] != "passed"]
    return {
        "status": "passed" if not failed else "warning",
        "failed_count": len(failed),
        "gates": gates,
        "message": "候选质量门禁通过。"
        if not failed
        else "候选未通过研究质量门禁，仍可确认，但需要记录风险并预期后续准入可能阻断。",
    }


def _evaluate_gate(
    definition: CandidateGateDefinition,
    metrics: Mapping[str, object],
) -> dict[str, object]:
    raw_value = metrics.get(definition.metric_key)
    observed = _decimal(raw_value)
    if observed is None:
        return {
            "gate_id": definition.gate_id,
            "label": definition.label,
            "metric_key": definition.metric_key,
            "operator": definition.operator,
            "threshold": _decimal_string(definition.threshold),
            "observed": "" if raw_value is None else str(raw_value),
            "unit": definition.unit,
            "status": "missing",
        }

    passed = observed >= definition.threshold if definition.operator == ">=" else observed <= definition.threshold
    return {
        "gate_id": definition.gate_id,
        "label": definition.label,
        "metric_key": definition.metric_key,
        "operator": definition.operator,
        "threshold": _decimal_string(definition.threshold),
        "observed": _decimal_string(observed),
        "unit": definition.unit,
        "status": "passed" if passed else "warning",
    }


def _decimal(value: object) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _decimal_string(value: Decimal) -> str:
    return format(value, "f")
