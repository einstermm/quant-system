from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.sandbox_export_acceptance import build_sandbox_export_acceptance
from packages.adapters.hummingbot.sandbox_reconciliation import replay_sandbox_events_from_manifest


class HummingbotSandboxExportAcceptanceTest(TestCase):
    def test_accepts_clean_hummingbot_export(self) -> None:
        manifest = _manifest()
        with TemporaryDirectory() as directory:
            event_path = Path(directory) / "events.jsonl"
            event_path.write_text("{}\n", encoding="utf-8")
            result = build_sandbox_export_acceptance(
                manifest=manifest,
                prepare_report=_prepare_report("sandbox_prepared"),
                events=replay_sandbox_events_from_manifest(
                    manifest=manifest,
                    starting_quote_balance=Decimal("1000"),
                ),
                event_jsonl=event_path,
                output_dir=Path(directory) / "acceptance",
                session_id="unit-session",
                event_source="hummingbot_export",
                starting_quote_balance=Decimal("1000"),
                quote_asset="USDT",
                environment=_environment(live=False),
                allow_warnings=False,
            )

            self.assertTrue((Path(result.output_dir) / "acceptance.json").exists())

        self.assertEqual("sandbox_export_accepted", result.decision)
        self.assertEqual("sandbox_reconciled", result.reconciliation_summary["decision"])
        self.assertEqual("sandbox_session_ready", result.session_gate_summary["decision"])
        self.assertEqual("sandbox_package_ready", result.package_summary["decision"])

    def test_replay_export_returns_warning(self) -> None:
        manifest = _manifest()
        with TemporaryDirectory() as directory:
            event_path = Path(directory) / "events.jsonl"
            event_path.write_text("{}\n", encoding="utf-8")
            result = build_sandbox_export_acceptance(
                manifest=manifest,
                prepare_report=_prepare_report("sandbox_prepared"),
                events=replay_sandbox_events_from_manifest(
                    manifest=manifest,
                    starting_quote_balance=Decimal("1000"),
                ),
                event_jsonl=event_path,
                output_dir=Path(directory) / "acceptance",
                session_id="unit-session",
                event_source="replay",
                starting_quote_balance=Decimal("1000"),
                quote_asset="USDT",
                environment=_environment(live=False),
                allow_warnings=True,
            )

        self.assertEqual("sandbox_export_accepted_with_warnings", result.decision)
        self.assertTrue(any(alert.title == "Replay acceptance only" for alert in result.alerts))

    def test_blocks_live_environment(self) -> None:
        manifest = _manifest()
        with TemporaryDirectory() as directory:
            event_path = Path(directory) / "events.jsonl"
            event_path.write_text("{}\n", encoding="utf-8")
            result = build_sandbox_export_acceptance(
                manifest=manifest,
                prepare_report=_prepare_report("sandbox_prepared"),
                events=replay_sandbox_events_from_manifest(
                    manifest=manifest,
                    starting_quote_balance=Decimal("1000"),
                ),
                event_jsonl=event_path,
                output_dir=Path(directory) / "acceptance",
                session_id="unit-session",
                event_source="hummingbot_export",
                starting_quote_balance=Decimal("1000"),
                quote_asset="USDT",
                environment=_environment(live=True),
                allow_warnings=True,
            )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Session gate blocked" for alert in result.alerts))


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "hummingbot_sandbox_manifest_v1",
        "strategy_id": "unit_strategy",
        "account_id": "paper-main",
        "connector_name": "binance_paper_trade",
        "controller_name": "unit_controller",
        "live_trading_enabled": False,
        "total_notional": "500",
        "controller_configs": [{"trading_pair": "BTC-USDT"}],
        "orders": [
            {
                "client_order_id": "order-1",
                "trading_pair": "BTC-USDT",
                "side": "buy",
                "amount": "0.01",
                "price": "25000",
                "expected_fee_quote": "0.25",
            },
            {
                "client_order_id": "order-2",
                "trading_pair": "XRP-USDT",
                "side": "buy",
                "amount": "100",
                "price": "2.5",
                "expected_fee_quote": "0.25",
            },
        ],
    }


def _prepare_report(decision: str) -> dict[str, object]:
    return {"decision": decision, "alerts": []}


def _environment(*, live: bool) -> dict[str, object]:
    return {
        "live_trading_enabled": live,
        "global_kill_switch": True,
        "hummingbot_api_base_url_configured": False,
        "exchange_key_env_detected": False,
    }
