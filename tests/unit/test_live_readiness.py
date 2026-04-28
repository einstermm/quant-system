from decimal import Decimal
from unittest import TestCase

from packages.reporting.live_readiness import (
    LiveReadinessThresholds,
    build_live_readiness_report,
)


class LiveReadinessTest(TestCase):
    def test_ready_with_warnings_for_clean_observation_and_missing_alert_channel(self) -> None:
        report = build_live_readiness_report(
            observation_review=_observation(decision="hummingbot_observation_window_ready_with_warnings"),
            acceptance_report=_acceptance(decision="sandbox_export_accepted_with_warnings"),
            daily_report=_daily_report(status="daily_report_ready_with_warnings"),
            risk_config=_risk_config(max_order_notional="1000"),
            environment=_environment(alert_channel_configured=False),
            session_id="unit",
            strategy_id="strategy",
            allow_warnings=True,
            thresholds=LiveReadinessThresholds(max_initial_live_order_notional=Decimal("250")),
        )

        self.assertEqual("live_preflight_ready_with_warnings", report.decision)
        self.assertFalse(any(alert.severity == "CRITICAL" for alert in report.alerts))
        self.assertTrue(any(alert.title == "Alert channel missing" for alert in report.alerts))

    def test_blocks_when_live_trading_is_already_enabled(self) -> None:
        report = build_live_readiness_report(
            observation_review=_observation(decision="hummingbot_observation_window_ready"),
            acceptance_report=_acceptance(decision="sandbox_export_accepted"),
            daily_report=_daily_report(status="daily_report_ready"),
            risk_config=_risk_config(),
            environment={**_environment(), "live_trading_enabled": True},
            session_id="unit",
            strategy_id="strategy",
            allow_warnings=True,
        )

        self.assertEqual("live_preflight_blocked", report.decision)
        self.assertTrue(any(alert.title == "Live trading enabled" for alert in report.alerts))

    def test_blocks_when_observation_is_short(self) -> None:
        observation = _observation(decision="hummingbot_observation_window_ready")
        observation["event_window"]["duration_hours"] = "1.5"
        report = build_live_readiness_report(
            observation_review=observation,
            acceptance_report=_acceptance(decision="sandbox_export_accepted"),
            daily_report=_daily_report(status="daily_report_ready"),
            risk_config=_risk_config(),
            environment=_environment(),
            session_id="unit",
            strategy_id="strategy",
            allow_warnings=True,
        )

        self.assertEqual("live_preflight_blocked", report.decision)
        self.assertTrue(any(alert.title == "Observation window too short" for alert in report.alerts))


def _observation(*, decision: str) -> dict[str, object]:
    return {
        "decision": decision,
        "event_window": {
            "duration_hours": "2.0",
            "event_count": 100,
        },
        "reconciliation_summary": {
            "submitted_orders": 2,
            "filled_orders": 2,
            "terminal_orders": 2,
            "failed_orders": 0,
            "canceled_orders": 0,
            "unknown_client_order_ids": [],
            "missing_terminal_orders": [],
        },
    }


def _acceptance(*, decision: str) -> dict[str, object]:
    return {
        "decision": decision,
        "event_source": "hummingbot_export",
        "session_gate_summary": {
            "decision": "sandbox_session_ready_with_warnings" if decision.endswith("_with_warnings") else "sandbox_session_ready",
            "live_trading_enabled": False,
            "exchange_key_env_detected": False,
        },
    }


def _daily_report(*, status: str) -> dict[str, object]:
    return {
        "status": status,
        "trading_summary": {
            "filled_orders": 2,
            "total_fee_quote": "1",
        },
        "balance_summary": {
            "quote_balance_delta": "-100",
        },
        "alerts": [],
    }


def _risk_config(*, max_order_notional: str = "100") -> dict[str, object]:
    return {
        "max_order_notional": max_order_notional,
        "max_symbol_notional": "500",
        "max_gross_notional": "1000",
        "max_daily_loss": "50",
        "max_drawdown_pct": "0.1",
    }


def _environment(**overrides: object) -> dict[str, object]:
    environment = {
        "live_trading_enabled": False,
        "global_kill_switch": True,
        "exchange_key_env_detected": False,
        "hummingbot_api_base_url_configured": True,
        "alert_channel_configured": True,
    }
    environment.update(overrides)
    return environment
