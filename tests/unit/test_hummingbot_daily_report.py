from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import TestCase

from packages.adapters.hummingbot.sandbox_reconciliation import SandboxRuntimeEvent
from packages.reporting.daily_report import build_hummingbot_daily_report


class HummingbotDailyReportTest(TestCase):
    def test_builds_daily_report_with_balance_and_fee_summary(self) -> None:
        start = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
        report = build_hummingbot_daily_report(
            events=(
                SandboxRuntimeEvent(
                    event_id="session:start",
                    event_type="session_started",
                    created_at=start,
                ),
                SandboxRuntimeEvent(
                    event_id="balance:usdt:start",
                    event_type="balance",
                    created_at=start,
                    balance_asset="USDT",
                    balance_total=Decimal("1000"),
                ),
                SandboxRuntimeEvent(
                    event_id="order-1:submitted",
                    event_type="submitted",
                    created_at=start,
                    client_order_id="order-1",
                    trading_pair="BTC-USDT",
                    side="buy",
                ),
                SandboxRuntimeEvent(
                    event_id="order-1:filled",
                    event_type="filled",
                    created_at=start + timedelta(seconds=5),
                    client_order_id="order-1",
                    trading_pair="BTC-USDT",
                    side="buy",
                    filled_amount=Decimal("0.01"),
                    average_fill_price=Decimal("50000"),
                    fee_quote=Decimal("0.5"),
                ),
                SandboxRuntimeEvent(
                    event_id="balance:usdt:end",
                    event_type="balance",
                    created_at=start + timedelta(hours=2),
                    balance_asset="USDT",
                    balance_total=Decimal("499.5"),
                ),
                SandboxRuntimeEvent(
                    event_id="session:done",
                    event_type="session_completed",
                    created_at=start + timedelta(hours=2),
                ),
            ),
            observation_review={"alerts": []},
            session_id="unit",
            strategy_id="strategy",
        )

        self.assertEqual("daily_report_ready", report.status)
        self.assertEqual("1", str(report.trading_summary["filled_orders"]))
        self.assertEqual("0.5", report.trading_summary["total_fee_quote"])
        self.assertEqual("-500.5", report.balance_summary["quote_balance_delta"])

    def test_carries_observation_warnings(self) -> None:
        start = datetime(2026, 4, 27, 0, 0, tzinfo=UTC)
        report = build_hummingbot_daily_report(
            events=(
                SandboxRuntimeEvent(event_id="start", event_type="session_started", created_at=start),
                SandboxRuntimeEvent(event_id="done", event_type="session_completed", created_at=start),
            ),
            observation_review={
                "alerts": [
                    {
                        "severity": "WARN",
                        "title": "Fill price drift",
                        "message": "Carry forward.",
                    }
                ]
            },
            session_id="unit",
            strategy_id="strategy",
        )

        self.assertEqual("daily_report_ready_with_warnings", report.status)
        self.assertTrue(any(alert.title == "Observation warnings carried" for alert in report.alerts))
