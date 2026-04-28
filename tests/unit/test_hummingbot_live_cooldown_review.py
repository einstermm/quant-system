import json
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from packages.adapters.hummingbot.live_cooldown_review import build_live_cooldown_review


class HummingbotLiveCooldownReviewTest(TestCase):
    def test_marks_cooldown_active_without_blocking_clean_post_trade(self) -> None:
        completed = datetime(2026, 4, 28, 2, 34, 33, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_jsonl = root / "events.jsonl"
            config = root / "runner.yml"
            _write_event_log(event_jsonl, completed)
            config.write_text("live_order_submission_armed: false\n", encoding="utf-8")

            review = build_live_cooldown_review(
                post_trade_report=_post_trade_report(),
                event_jsonl=event_jsonl,
                runner_config_yml=config,
                session_id="phase_6_8",
                minimum_cooldown_hours=Decimal("24"),
                generated_at=completed + timedelta(hours=1),
                manual_open_orders_check={
                    "checked_at": "2026-04-28T02:55:38+00:00",
                    "abnormal_open_orders_found": False,
                    "evidence": "Operator reported no abnormal open orders.",
                },
                runner_container_status="not_found",
                hummingbot_container_status="Exited (137)",
            )

            self.assertEqual("live_cooldown_active_with_warnings", review.status)
            self.assertFalse(review.cooldown_window["cooldown_elapsed"])
            self.assertFalse(review.operational_checks["runner_config_armed"])
            self.assertEqual("confirmed_clean", review.manual_checks["open_orders_check_status"])
            self.assertFalse(review.expansion_controls["expansion_allowed"])
            self.assertTrue(any(alert.title == "Cooldown active" for alert in review.alerts))
            self.assertFalse(
                any(alert.title == "Manual open orders check pending" for alert in review.alerts)
            )

    def test_blocks_when_runner_is_still_running(self) -> None:
        completed = datetime(2026, 4, 28, 2, 34, 33, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_jsonl = root / "events.jsonl"
            config = root / "runner.yml"
            _write_event_log(event_jsonl, completed)
            config.write_text("live_order_submission_armed: false\n", encoding="utf-8")

            review = build_live_cooldown_review(
                post_trade_report=_post_trade_report(),
                event_jsonl=event_jsonl,
                runner_config_yml=config,
                session_id="phase_6_8",
                minimum_cooldown_hours=Decimal("24"),
                generated_at=completed + timedelta(hours=25),
                runner_container_status="Up 1 minute",
                hummingbot_container_status="Exited (137)",
            )

            self.assertEqual("live_cooldown_blocked", review.status)
            self.assertTrue(
                any(alert.title == "Live runner still running" for alert in review.alerts)
            )


def _write_event_log(path: Path, completed: datetime) -> None:
    records = [
        {"event_type": "session_started", "created_at": "2026-04-28T02:34:01+00:00"},
        {"event_type": "session_completed", "created_at": completed.isoformat()},
    ]
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record))
            file.write("\n")


def _post_trade_report() -> dict[str, object]:
    return {
        "status": "live_post_trade_reconciled_with_warnings",
        "strategy_id": "crypto_relative_strength_v1",
        "account_id": "binance-main-spot",
        "order_checks": {
            "submitted_orders": 1,
            "filled_orders": 1,
            "db_fills": 1,
            "missing_submissions": [],
            "missing_fills": [],
            "missing_db_fills": [],
        },
        "fill_summary": {
            "gross_quote_notional": "49.266880",
            "net_base_quantity": "0.00063936",
        },
        "balance_checks": {"mismatches": []},
        "risk_checks": {
            "allowed_pairs": ["BTC-USDT", "ETH-USDT"],
            "max_batch_notional": "50",
            "max_order_notional": "50",
            "total_notional_inside_cap": True,
            "order_count_inside_cap": True,
            "price_deviation_inside_cap": True,
        },
        "alerts": [
            {
                "severity": "WARN",
                "title": "Validation tax export",
                "message": "Validation only.",
            }
        ],
    }
