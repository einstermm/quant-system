import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.sandbox_package import build_sandbox_package


class HummingbotSandboxPackageTest(TestCase):
    def test_builds_package_with_replay_warning(self) -> None:
        with TemporaryDirectory() as directory:
            result = build_sandbox_package(
                manifest=_manifest(),
                session_gate=_session_gate(decision="sandbox_session_ready_with_warnings", event_source="replay"),
                output_dir=Path(directory) / "package",
                allow_warnings=True,
            )

            output_dir = Path(result.output_dir)
            summary = json.loads((output_dir / "package_summary.json").read_text(encoding="utf-8"))
            self.assertTrue((output_dir / "orders.jsonl").exists())
            self.assertTrue((output_dir / "controller_configs" / "btc_usdt.json").exists())

        self.assertEqual("sandbox_package_ready_with_warnings", result.decision)
        self.assertEqual(2, result.summary["order_count"])
        self.assertEqual(result.decision, summary["decision"])
        self.assertTrue(any(alert.title == "Replay package only" for alert in result.alerts))

    def test_blocks_warning_without_allowance(self) -> None:
        with TemporaryDirectory() as directory:
            result = build_sandbox_package(
                manifest=_manifest(),
                session_gate=_session_gate(decision="sandbox_session_ready_with_warnings", event_source="replay"),
                output_dir=Path(directory) / "package",
                allow_warnings=False,
            )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Session gate has warnings" for alert in result.alerts))

    def test_blocks_live_manifest(self) -> None:
        manifest = _manifest()
        manifest["live_trading_enabled"] = True
        with TemporaryDirectory() as directory:
            result = build_sandbox_package(
                manifest=manifest,
                session_gate=_session_gate(decision="sandbox_session_ready", event_source="hummingbot_export"),
                output_dir=Path(directory) / "package",
                allow_warnings=True,
            )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Live trading enabled" for alert in result.alerts))


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "hummingbot_sandbox_manifest_v1",
        "strategy_id": "unit_strategy",
        "account_id": "paper-main",
        "connector_name": "binance_paper_trade",
        "controller_name": "unit_controller",
        "live_trading_enabled": False,
        "total_notional": "500",
        "controller_configs": [
            {
                "controller_name": "unit_controller",
                "connector_name": "binance_paper_trade",
                "trading_pair": "BTC-USDT",
                "total_amount_quote": "500",
                "executor_count": 2,
            }
        ],
        "orders": [
            {
                "client_order_id": "order-1",
                "trading_pair": "BTC-USDT",
                "side": "buy",
                "amount": "0.01",
                "price": "25000",
            },
            {
                "client_order_id": "order-2",
                "trading_pair": "BTC-USDT",
                "side": "sell",
                "amount": "0.01",
                "price": "25000",
            },
        ],
    }


def _session_gate(*, decision: str, event_source: str) -> dict[str, object]:
    return {
        "decision": decision,
        "session_id": "unit-session",
        "event_source": event_source,
        "alerts": [],
    }
