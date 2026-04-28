from decimal import Decimal
from unittest import TestCase

from packages.reporting.live_activation import build_live_activation_checklist


class LiveActivationTest(TestCase):
    def test_blocks_when_alert_channel_missing(self) -> None:
        report = build_live_activation_checklist(
            live_readiness=_live_readiness(),
            daily_report=_daily_report(),
            tax_export_summary=_tax_summary(),
            live_risk_config=_risk_config(),
            environment={
                "live_trading_enabled": False,
                "global_kill_switch": True,
                "alert_channel_configured": False,
                "exchange_key_env_detected": False,
            },
            session_id="unit",
            strategy_id="strategy",
            max_initial_live_order_notional=Decimal("250"),
        )

        self.assertEqual("live_activation_blocked", report.decision)
        self.assertTrue(any(item.item_id == "alert_channel" and item.status == "FAIL" for item in report.checklist))

    def test_pending_manual_signoff_when_automatic_items_pass(self) -> None:
        report = build_live_activation_checklist(
            live_readiness=_live_readiness(),
            daily_report=_daily_report(),
            tax_export_summary=_tax_summary(),
            live_risk_config=_risk_config(),
            environment={
                "live_trading_enabled": False,
                "global_kill_switch": True,
                "alert_channel_configured": True,
                "exchange_key_env_detected": True,
            },
            session_id="unit",
            strategy_id="strategy",
            max_initial_live_order_notional=Decimal("250"),
        )

        self.assertEqual("live_activation_pending_manual_signoff", report.decision)
        self.assertTrue(any(item.status == "MANUAL_REQUIRED" for item in report.checklist))

    def test_ready_when_manual_items_are_signed(self) -> None:
        report = build_live_activation_checklist(
            live_readiness=_live_readiness(),
            daily_report=_daily_report(),
            tax_export_summary=_tax_summary(),
            live_risk_config=_risk_config(),
            environment={
                "live_trading_enabled": False,
                "global_kill_switch": True,
                "alert_channel_configured": True,
                "exchange_key_env_detected": True,
            },
            session_id="unit",
            strategy_id="strategy",
            max_initial_live_order_notional=Decimal("250"),
            manual_credentials_reviewed=True,
            manual_exchange_allowlist_reviewed=True,
            manual_operator_signoff=True,
        )

        self.assertEqual("live_activation_ready", report.decision)


def _live_readiness() -> dict[str, object]:
    return {
        "decision": "live_preflight_ready_with_warnings",
        "observation_summary": {
            "filled_orders": 8,
        },
        "artifacts": {
            "observation_review_json": "observation.json",
        },
    }


def _daily_report() -> dict[str, object]:
    return {
        "status": "daily_report_ready_with_warnings",
    }


def _tax_summary() -> dict[str, object]:
    return {
        "status": "tax_export_ready_with_warnings",
        "row_count": 8,
    }


def _risk_config() -> dict[str, object]:
    return {
        "max_order_notional": "250",
        "max_symbol_notional": "500",
        "max_gross_notional": "1000",
        "max_daily_loss": "50",
        "max_drawdown_pct": "0.05",
    }
