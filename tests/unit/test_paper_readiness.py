import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.reporting.paper_readiness import (
    PaperReadinessThresholds,
    build_paper_readiness_report,
    write_report_json,
    write_report_markdown,
    write_risk_off_runbook,
)


class PaperReadinessTest(TestCase):
    def test_builds_ready_with_warnings_report(self) -> None:
        report = build_paper_readiness_report(
            walk_forward_payload=_walk_forward_payload(),
            capacity_stress_payload=_capacity_stress_payload(),
            thresholds=PaperReadinessThresholds(min_capacity_equity=Decimal("100000")),
        )

        self.assertEqual("crypto_relative_strength_v1", report.strategy_id)
        self.assertEqual("paper_ready_with_warnings", report.status)
        self.assertEqual(Decimal("0.70"), report.summary["positive_fold_ratio"])
        self.assertEqual(Decimal("231186"), report.capacity["min_estimated_capacity_equity"])
        self.assertTrue(any(alert.severity == "WARN" for alert in report.alerts))
        self.assertFalse(any(alert.severity == "CRITICAL" for alert in report.alerts))

    def test_blocks_when_capacity_is_too_low(self) -> None:
        report = build_paper_readiness_report(
            walk_forward_payload=_walk_forward_payload(),
            thresholds=PaperReadinessThresholds(min_capacity_equity=Decimal("500000")),
        )

        self.assertEqual("blocked", report.status)
        self.assertTrue(any(alert.title == "Capacity below minimum" for alert in report.alerts))

    def test_writes_report_outputs(self) -> None:
        report = build_paper_readiness_report(walk_forward_payload=_walk_forward_payload())

        with TemporaryDirectory() as directory:
            json_path = write_report_json(report, Path(directory) / "readiness.json")
            md_path = write_report_markdown(report, Path(directory) / "readiness.md")
            runbook_path = write_risk_off_runbook(report, Path(directory) / "runbook.md")

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = md_path.read_text(encoding="utf-8")
            runbook = runbook_path.read_text(encoding="utf-8")

        self.assertEqual(report.status, payload["status"])
        self.assertIn("Paper Readiness Report", markdown)
        self.assertIn("Risk-Off Recovery Runbook", runbook)


def _walk_forward_payload() -> dict[str, object]:
    folds = []
    returns = (
        Decimal("0.01"),
        Decimal("0.78"),
        Decimal("0.31"),
        Decimal("0.02"),
        Decimal("-0.03"),
        Decimal("0.44"),
        Decimal("-0.02"),
        Decimal("0.03"),
        Decimal("0.04"),
        Decimal("-0.04"),
    )
    for index, value in enumerate(returns, start=1):
        folds.append(
            {
                "selected_run": {
                    "test_metrics": {
                        "total_return": str(value),
                        "max_drawdown": "0.10",
                        "tail_loss": "0.05",
                        "max_observed_participation_rate": "0.0008",
                        "estimated_participation_capacity_equity": "231186",
                        "participation_capped_count": 0,
                        "min_order_skipped_count": 0,
                        "risk_off_bars": 10 if index == 1 else 0,
                        "recovery_bars": 0,
                        "drawdown_stop_count": 1 if index == 1 else 0,
                    }
                }
            }
        )
    return {
        "strategy_id": "crypto_relative_strength_v1",
        "experiment_id": "unit_phase_3_9",
        "summary": {
            "folds": 10,
            "selected_positive_folds": 7,
            "average_selected_test_return": "0.154",
            "median_selected_test_return": "0.026",
            "worst_selected_test_return": "-0.047",
            "best_selected_test_return": "0.78",
            "worst_selected_test_drawdown": "0.106",
            "worst_selected_test_tail_loss": "0.052",
        },
        "folds": folds,
    }


def _capacity_stress_payload() -> dict[str, object]:
    return {
        "metrics": {
            "participation_capped_count": 14,
            "participation_capped_notional": "668397",
        }
    }
