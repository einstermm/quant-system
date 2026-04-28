from decimal import Decimal
from datetime import UTC, datetime
from unittest import TestCase

from packages.adapters.hummingbot.observation_review import (
    HummingbotObservationThresholds,
    build_hummingbot_observation_review,
)
from packages.adapters.hummingbot.sandbox_reconciliation import SandboxRuntimeEvent


class HummingbotObservationReviewTest(TestCase):
    def test_accepts_real_export_with_warnings(self) -> None:
        result = build_hummingbot_observation_review(
            acceptance_report=_acceptance(decision="sandbox_export_accepted_with_warnings"),
            reconciliation_report=_reconciliation(with_warnings=True),
            events=_events(),
            session_id="unit",
            allow_warnings=True,
            thresholds=HummingbotObservationThresholds(target_window_hours=Decimal("2")),
        )

        self.assertEqual("hummingbot_observation_window_ready_with_warnings", result.decision)
        self.assertEqual(2, result.reconciliation_summary["expected_orders"])
        self.assertTrue(any(alert.title == "Observation window short" for alert in result.alerts))
        self.assertTrue(result.carry_forward_warnings["submitted_amount_adjustments"])

    def test_blocks_replay_source(self) -> None:
        result = build_hummingbot_observation_review(
            acceptance_report={**_acceptance(decision="sandbox_export_accepted"), "event_source": "replay"},
            reconciliation_report=_reconciliation(with_warnings=False),
            events=_events(),
            session_id="unit",
            allow_warnings=True,
        )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Real Hummingbot export missing" for alert in result.alerts))

    def test_blocks_order_mismatch(self) -> None:
        reconciliation = _reconciliation(with_warnings=False)
        reconciliation["order_checks"]["filled_orders"] = 1

        result = build_hummingbot_observation_review(
            acceptance_report=_acceptance(decision="sandbox_export_accepted"),
            reconciliation_report=reconciliation,
            events=_events(),
            session_id="unit",
            allow_warnings=False,
        )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Order filled mismatch" for alert in result.alerts))


def _acceptance(*, decision: str) -> dict[str, object]:
    return {
        "decision": decision,
        "event_source": "hummingbot_export",
        "output_dir": "reports/unit",
        "session_gate_summary": {
            "decision": "sandbox_session_ready_with_warnings" if decision.endswith("_with_warnings") else "sandbox_session_ready",
            "live_trading_enabled": False,
            "exchange_key_env_detected": False,
        },
    }


def _reconciliation(*, with_warnings: bool) -> dict[str, object]:
    return {
        "decision": "sandbox_reconciled_with_warnings" if with_warnings else "sandbox_reconciled",
        "event_counts": {"submitted": 2, "filled": 2, "balance": 1},
        "order_checks": {
            "expected_orders": 2,
            "submitted_orders": 2,
            "filled_orders": 2,
            "terminal_orders": 2,
            "failed_orders": 0,
            "canceled_orders": 0,
            "unknown_client_order_ids": [],
            "missing_submissions": [],
            "missing_terminal_orders": [],
            "order_exception_events": 0,
            "disconnect_events": 0,
            "balance_anomaly_events": 0,
        },
        "fill_checks": {
            "submitted_amount_adjustments": [
                {
                    "client_order_id": "order-2",
                    "manifest_amount": "100",
                    "submitted_amount": "99.8",
                    "diff": "0.2",
                    "reason": "paper_available_balance_cap",
                }
            ]
            if with_warnings
            else [],
            "price_warnings": [{"client_order_id": "order-2"}] if with_warnings else [],
            "fee_warnings": [{"client_order_id": "order-2"}] if with_warnings else [],
        },
        "balance_checks": {
            "status": "skipped" if with_warnings else "checked",
            "balance_events": 1,
            "balance_mismatches": [],
        },
    }


def _events() -> tuple[SandboxRuntimeEvent, ...]:
    start = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
    return (
        SandboxRuntimeEvent(
            event_id="order-1:submitted",
            event_type="submitted",
            created_at=start,
            client_order_id="order-1",
            trading_pair="BTC-USDT",
        ),
        SandboxRuntimeEvent(
            event_id="order-1:filled",
            event_type="filled",
            created_at=start,
            client_order_id="order-1",
            trading_pair="BTC-USDT",
        ),
        SandboxRuntimeEvent(
            event_id="balance:USDT",
            event_type="balance",
            created_at=start,
            balance_asset="USDT",
            balance_total=Decimal("1000"),
        ),
    )
