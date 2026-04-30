"""Strategy-specific evidence inputs for paper readiness jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ReadinessEvidence:
    strategy_id: str
    walk_forward_json: Path
    capacity_stress_json: Path | None


READINESS_EVIDENCE_BY_STRATEGY: dict[str, ReadinessEvidence] = {
    "crypto_relative_strength_v1": ReadinessEvidence(
        strategy_id="crypto_relative_strength_v1",
        walk_forward_json=Path(
            "reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_walk_forward.json"
        ),
        capacity_stress_json=Path("reports/backtests/crypto_relative_strength_v1_phase_3_8_capacity_stress_1m.json"),
    ),
    "crypto_momentum_v1": ReadinessEvidence(
        strategy_id="crypto_momentum_v1",
        walk_forward_json=Path("reports/backtests/crypto_momentum_v1_phase_3_3_walk_forward.json"),
        capacity_stress_json=None,
    ),
}


def readiness_evidence_for_strategy(strategy_id: str) -> ReadinessEvidence:
    evidence = READINESS_EVIDENCE_BY_STRATEGY.get(strategy_id)
    if evidence is None:
        raise ValueError(f"no paper readiness evidence mapping for strategy: {strategy_id}")
    return evidence
