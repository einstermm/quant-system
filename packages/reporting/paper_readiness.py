"""Paper trading readiness report builder."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert
from packages.backtesting.result import decimal_to_str


@dataclass(frozen=True, slots=True)
class PaperReadinessThresholds:
    min_positive_fold_ratio: Decimal = Decimal("0.70")
    min_median_return: Decimal = Decimal("0")
    max_worst_return_loss: Decimal = Decimal("0.05")
    max_worst_drawdown: Decimal = Decimal("0.12")
    max_worst_tail_loss: Decimal = Decimal("0.06")
    max_participation_rate: Decimal = Decimal("0.02")
    min_capacity_equity: Decimal = Decimal("100000")
    max_min_order_skipped_count: int = 0
    max_participation_capped_count: int = 0
    best_to_average_warning_ratio: Decimal = Decimal("4")

    def to_dict(self) -> dict[str, object]:
        return {
            "min_positive_fold_ratio": decimal_to_str(self.min_positive_fold_ratio),
            "min_median_return": decimal_to_str(self.min_median_return),
            "max_worst_return_loss": decimal_to_str(self.max_worst_return_loss),
            "max_worst_drawdown": decimal_to_str(self.max_worst_drawdown),
            "max_worst_tail_loss": decimal_to_str(self.max_worst_tail_loss),
            "max_participation_rate": decimal_to_str(self.max_participation_rate),
            "min_capacity_equity": decimal_to_str(self.min_capacity_equity),
            "max_min_order_skipped_count": self.max_min_order_skipped_count,
            "max_participation_capped_count": self.max_participation_capped_count,
            "best_to_average_warning_ratio": decimal_to_str(self.best_to_average_warning_ratio),
        }


@dataclass(frozen=True, slots=True)
class PaperReadinessReport:
    strategy_id: str
    experiment_id: str
    generated_at: datetime
    status: str
    summary: dict[str, Decimal | int]
    capacity: dict[str, Decimal | int]
    thresholds: PaperReadinessThresholds
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "experiment_id": self.experiment_id,
            "generated_at": self.generated_at.isoformat(),
            "status": self.status,
            "summary": _decimal_dict(self.summary),
            "capacity": _decimal_dict(self.capacity),
            "thresholds": self.thresholds.to_dict(),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Paper Readiness Report: {self.strategy_id}",
            "",
            f"- Experiment: `{self.experiment_id}`",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Status: `{self.status}`",
            "",
            "## Summary",
            "",
            f"- Positive folds: `{self.summary['positive_folds']}/{self.summary['folds']}`",
            f"- Positive fold ratio: `{_pct(self.summary['positive_fold_ratio'])}`",
            f"- Average selected test return: `{_pct(self.summary['average_selected_test_return'])}`",
            f"- Median selected test return: `{_pct(self.summary['median_selected_test_return'])}`",
            f"- Worst selected test return: `{_pct(self.summary['worst_selected_test_return'])}`",
            f"- Worst selected test drawdown: `{_pct(self.summary['worst_selected_test_drawdown'])}`",
            f"- Worst selected test tail loss: `{_pct(self.summary['worst_selected_test_tail_loss'])}`",
            "",
            "## Capacity",
            "",
            f"- Max selected test participation: `{_pct(self.capacity['max_observed_participation_rate'])}`",
            f"- Minimum estimated capacity equity: `{self.capacity['min_estimated_capacity_equity']}`",
            f"- Participation capped orders: `{self.capacity['participation_capped_count_sum']}`",
            f"- Min-order skipped orders: `{self.capacity['min_order_skipped_count_sum']}`",
            f"- Risk-off bars: `{self.capacity['risk_off_bars_sum']}`",
            f"- Recovery bars: `{self.capacity['recovery_bars_sum']}`",
            "",
            "## Alerts",
            "",
        ]
        if self.alerts:
            lines.extend(
                f"- `{alert.severity}` {alert.title}: {alert.message}"
                for alert in self.alerts
            )
        else:
            lines.append("- None")

        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def build_paper_readiness_report(
    *,
    walk_forward_payload: dict[str, Any],
    thresholds: PaperReadinessThresholds | None = None,
    capacity_stress_payload: dict[str, Any] | None = None,
) -> PaperReadinessReport:
    limits = thresholds or PaperReadinessThresholds()
    summary = _summary_metrics(walk_forward_payload)
    capacity = _capacity_metrics(walk_forward_payload, capacity_stress_payload)
    alerts = _build_alerts(summary=summary, capacity=capacity, thresholds=limits)
    status = _status(alerts)
    return PaperReadinessReport(
        strategy_id=str(walk_forward_payload["strategy_id"]),
        experiment_id=str(walk_forward_payload["experiment_id"]),
        generated_at=datetime.now(tz=UTC),
        status=status,
        summary=summary,
        capacity=capacity,
        thresholds=limits,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(status, alerts),
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_report_json(report: PaperReadinessReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_report_markdown(report: PaperReadinessReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def build_risk_off_runbook(report: PaperReadinessReport) -> str:
    return "\n".join(
        (
            "# Risk-Off Recovery Runbook",
            "",
            "## Trigger",
            "",
            "- Global drawdown stop is active.",
            "- Kill switch or manual risk-off has been activated.",
            "- Exchange/API/account reconciliation is unhealthy.",
            "",
            "## Immediate Actions",
            "",
            "1. Keep live trading disabled.",
            "2. Stop new order generation.",
            "3. Cancel open paper orders.",
            "4. Snapshot balances, positions, open orders, and latest market data.",
            "5. Record the alert title, timestamp, strategy id, and account id.",
            "",
            "## Recovery Checks",
            "",
            f"- Current readiness status: `{report.status}`.",
            "- Data freshness is within the configured heartbeat window.",
            "- No CRITICAL alerts remain open.",
            "- Paper account positions match internal positions.",
            "- Last 3 paper cycles have no rejected reconciliation checks.",
            "",
            "## Resume Rules",
            "",
            "1. Resume only in paper mode.",
            "2. Start with risk scale at 25% of configured target.",
            "3. Increase to 50%, 75%, then 100% only after clean monitoring cycles.",
            "4. Any new CRITICAL alert returns the strategy to risk-off.",
            "",
        )
    )


def write_risk_off_runbook(report: PaperReadinessReport, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_risk_off_runbook(report), encoding="utf-8")
    return output_path


def _summary_metrics(payload: dict[str, Any]) -> dict[str, Decimal | int]:
    raw = payload["summary"]
    folds = int(raw["folds"])
    positive = int(raw["selected_positive_folds"])
    return {
        "folds": folds,
        "positive_folds": positive,
        "positive_fold_ratio": Decimal(positive) / Decimal(folds),
        "average_selected_test_return": Decimal(str(raw["average_selected_test_return"])),
        "median_selected_test_return": Decimal(str(raw["median_selected_test_return"])),
        "worst_selected_test_return": Decimal(str(raw["worst_selected_test_return"])),
        "best_selected_test_return": Decimal(str(raw["best_selected_test_return"])),
        "worst_selected_test_drawdown": Decimal(str(raw["worst_selected_test_drawdown"])),
        "worst_selected_test_tail_loss": Decimal(str(raw["worst_selected_test_tail_loss"])),
    }


def _capacity_metrics(
    payload: dict[str, Any],
    capacity_stress_payload: dict[str, Any] | None,
) -> dict[str, Decimal | int]:
    test_metrics = [fold["selected_run"]["test_metrics"] for fold in payload["folds"]]
    max_participation = max(
        Decimal(str(metrics["max_observed_participation_rate"]))
        for metrics in test_metrics
    )
    min_capacity = min(
        Decimal(str(metrics["estimated_participation_capacity_equity"]))
        for metrics in test_metrics
    )
    capacity: dict[str, Decimal | int] = {
        "max_observed_participation_rate": max_participation,
        "min_estimated_capacity_equity": min_capacity,
        "participation_capped_count_sum": sum(
            int(metrics["participation_capped_count"]) for metrics in test_metrics
        ),
        "min_order_skipped_count_sum": sum(
            int(metrics["min_order_skipped_count"]) for metrics in test_metrics
        ),
        "risk_off_bars_sum": sum(int(metrics["risk_off_bars"]) for metrics in test_metrics),
        "recovery_bars_sum": sum(int(metrics["recovery_bars"]) for metrics in test_metrics),
        "drawdown_stop_count_sum": sum(
            int(metrics["drawdown_stop_count"]) for metrics in test_metrics
        ),
    }
    if capacity_stress_payload is not None:
        stress_metrics = capacity_stress_payload["metrics"]
        capacity["stress_participation_capped_count"] = int(
            stress_metrics["participation_capped_count"]
        )
        capacity["stress_participation_capped_notional"] = Decimal(
            str(stress_metrics["participation_capped_notional"])
        )
    return capacity


def _build_alerts(
    *,
    summary: dict[str, Decimal | int],
    capacity: dict[str, Decimal | int],
    thresholds: PaperReadinessThresholds,
) -> list[Alert]:
    alerts: list[Alert] = []
    if summary["positive_fold_ratio"] < thresholds.min_positive_fold_ratio:
        alerts.append(critical_alert("Positive fold ratio too low", "Walk-forward stability is below threshold."))
    if summary["median_selected_test_return"] < thresholds.min_median_return:
        alerts.append(critical_alert("Median return below threshold", "Median selected test return is negative."))
    if summary["worst_selected_test_return"] < -thresholds.max_worst_return_loss:
        alerts.append(critical_alert("Worst test loss too large", "Worst selected test fold breached loss threshold."))
    if summary["worst_selected_test_drawdown"] > thresholds.max_worst_drawdown:
        alerts.append(critical_alert("Worst drawdown too large", "Worst selected test drawdown breached threshold."))
    if summary["worst_selected_test_tail_loss"] > thresholds.max_worst_tail_loss:
        alerts.append(critical_alert("Tail loss too large", "Worst selected test tail loss breached threshold."))
    if capacity["max_observed_participation_rate"] > thresholds.max_participation_rate:
        alerts.append(critical_alert("Participation rate breached", "Observed participation exceeded configured cap."))
    if capacity["min_estimated_capacity_equity"] < thresholds.min_capacity_equity:
        alerts.append(critical_alert("Capacity below minimum", "Estimated capacity is too small for paper readiness."))
    if capacity["participation_capped_count_sum"] > thresholds.max_participation_capped_count:
        alerts.append(critical_alert("Orders capped by participation", "Selected folds required participation caps."))
    if capacity["min_order_skipped_count_sum"] > thresholds.max_min_order_skipped_count:
        alerts.append(critical_alert("Orders skipped by minimum notional", "Selected folds skipped orders by minimum notional."))

    average_return = summary["average_selected_test_return"]
    if average_return > Decimal("0") and (
        summary["best_selected_test_return"] / average_return
    ) > thresholds.best_to_average_warning_ratio:
        alerts.append(warning_alert("Return concentration", "Average return is heavily influenced by the best fold."))
    if capacity["risk_off_bars_sum"] > 0:
        alerts.append(warning_alert("Risk-off observed", "Selected test folds entered risk-off; recovery runbook is required."))
    if capacity.get("stress_participation_capped_count", 0) > 0:
        alerts.append(warning_alert("Capacity stress capped orders", "Larger capital stress run hit participation caps."))
    if not alerts:
        alerts.append(info_alert("Paper readiness checks passed", "No blocking paper readiness issues detected."))
    return alerts


def _status(alerts: tuple[Alert, ...] | list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "paper_ready_with_warnings"
    return "paper_ready"


def _recommended_actions(status: str, alerts: tuple[Alert, ...] | list[Alert]) -> tuple[str, ...]:
    actions = [
        "Keep live trading disabled.",
        "Run the candidate only in paper mode with explicit kill switch enabled.",
        "Generate and review this readiness report before every paper session.",
    ]
    if status == "blocked":
        actions.insert(0, "Do not start paper trading until CRITICAL alerts are resolved.")
    if any(alert.title == "Return concentration" for alert in alerts):
        actions.append("Review fold-level return distribution before increasing paper size.")
    if any(alert.title == "Risk-off observed" for alert in alerts):
        actions.append("Follow the generated risk-off recovery runbook before resuming after a stop.")
    if any(alert.title == "Capacity stress capped orders" for alert in alerts):
        actions.append("Do not scale capital above estimated participation capacity without new execution assumptions.")
    return tuple(actions)


def _decimal_dict(values: dict[str, Decimal | int]) -> dict[str, object]:
    return {
        key: decimal_to_str(value) if isinstance(value, Decimal) else value
        for key, value in values.items()
    }


def _pct(value: Decimal | int) -> str:
    if not isinstance(value, Decimal):
        value = Decimal(value)
    return f"{decimal_to_str(value * Decimal('100'))}%"
