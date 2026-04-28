from unittest import TestCase

from packages.adapters.hummingbot.sandbox_session import build_sandbox_session_gate


class HummingbotSandboxSessionGateTest(TestCase):
    def test_allows_clean_hummingbot_export_session(self) -> None:
        result = build_sandbox_session_gate(
            manifest=_manifest(live=False),
            prepare_report=_prepare_report("sandbox_prepared"),
            reconciliation_report=_reconciliation_report("sandbox_reconciled"),
            session_id="unit-session",
            event_source="hummingbot_export",
            artifacts={"event_jsonl_exists": True},
            environment=_environment(live=False),
            allow_warnings=False,
        )

        self.assertEqual("sandbox_session_ready", result.decision)
        self.assertFalse(any(alert.severity == "CRITICAL" for alert in result.alerts))

    def test_replay_source_is_ready_with_warning(self) -> None:
        result = build_sandbox_session_gate(
            manifest=_manifest(live=False),
            prepare_report=_prepare_report("sandbox_prepared"),
            reconciliation_report=_reconciliation_report("sandbox_reconciled"),
            session_id="unit-session",
            event_source="replay",
            artifacts={"event_jsonl_exists": True},
            environment=_environment(live=False),
            allow_warnings=False,
        )

        self.assertEqual("sandbox_session_ready_with_warnings", result.decision)
        self.assertTrue(any(alert.title == "External Hummingbot runtime pending" for alert in result.alerts))

    def test_blocks_when_live_trading_is_enabled(self) -> None:
        result = build_sandbox_session_gate(
            manifest=_manifest(live=False),
            prepare_report=_prepare_report("sandbox_prepared"),
            reconciliation_report=_reconciliation_report("sandbox_reconciled"),
            session_id="unit-session",
            event_source="hummingbot_export",
            artifacts={"event_jsonl_exists": True},
            environment=_environment(live=True),
            allow_warnings=False,
        )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Environment live trading enabled" for alert in result.alerts))

    def test_blocks_upstream_warning_without_allowance(self) -> None:
        result = build_sandbox_session_gate(
            manifest=_manifest(live=False),
            prepare_report=_prepare_report("sandbox_prepared_with_warnings"),
            reconciliation_report=_reconciliation_report("sandbox_reconciled"),
            session_id="unit-session",
            event_source="hummingbot_export",
            artifacts={"event_jsonl_exists": True},
            environment=_environment(live=False),
            allow_warnings=False,
        )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Sandbox prepare has warnings" for alert in result.alerts))


def _manifest(*, live: bool) -> dict[str, object]:
    return {
        "schema_version": "hummingbot_sandbox_manifest_v1",
        "strategy_id": "unit_strategy",
        "account_id": "paper-main",
        "connector_name": "binance_paper_trade",
        "controller_name": "unit_controller",
        "live_trading_enabled": live,
        "total_notional": "500",
        "controller_configs": [{"trading_pair": "BTC-USDT"}],
        "orders": [{"client_order_id": "order-1"}, {"client_order_id": "order-2"}],
    }


def _prepare_report(decision: str) -> dict[str, object]:
    return {"decision": decision, "alerts": []}


def _reconciliation_report(decision: str) -> dict[str, object]:
    return {
        "decision": decision,
        "event_counts": {"submitted": 2, "filled": 2, "balance": 2},
        "order_checks": {
            "submitted_orders": 2,
            "terminal_orders": 2,
            "filled_orders": 2,
            "unknown_client_order_ids": [],
            "missing_terminal_orders": [],
        },
        "balance_checks": {
            "balance_events": 2,
            "balance_mismatches": [],
        },
    }


def _environment(*, live: bool) -> dict[str, object]:
    return {
        "live_trading_enabled": live,
        "global_kill_switch": True,
        "hummingbot_api_base_url_configured": False,
        "exchange_key_env_detected": False,
    }
