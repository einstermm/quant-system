from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.cli_direct_paper_handoff import build_cli_direct_paper_handoff


class HummingbotCliDirectPaperHandoffTest(TestCase):
    def test_builds_direct_script_handoff(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_cli_direct_paper_handoff(
                manifest=_manifest(live=False),
                runtime_preflight=_runtime_preflight(),
                output_dir=Path(tmp) / "handoff",
                session_id="unit",
                hummingbot_root=Path(tmp) / "hummingbot",
                allow_warnings=False,
            )

            self.assertEqual("cli_direct_paper_handoff_ready", result.decision)
            script_source = Path(result.artifacts["script_source"]).read_text(encoding="utf-8")
            script_config = Path(result.artifacts["script_config"]).read_text(encoding="utf-8")
            self.assertIn("class QuantSystemCliPaperOrders", script_source)
            self.assertIn("did_fill_order", script_source)
            self.assertIn("heartbeat_interval_seconds", script_source)
            self.assertIn("session_completed", script_source)
            self.assertIn("script_file_name: \"quant_system_cli_paper_orders.py\"", script_config)
            self.assertIn('observation_min_runtime_seconds: "0"', script_config)
            self.assertIn('heartbeat_interval_seconds: "60"', script_config)
            self.assertIn("client_order_id: \"order-1\"", script_config)

    def test_builds_observation_window_config(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_cli_direct_paper_handoff(
                manifest=_manifest(live=False),
                runtime_preflight=_runtime_preflight(),
                output_dir=Path(tmp) / "handoff",
                session_id="unit",
                hummingbot_root=Path(tmp) / "hummingbot",
                allow_warnings=False,
                event_log_path="/home/hummingbot/data/unit_events.jsonl",
                script_config_name="unit_observation.yml",
                observation_min_runtime_seconds=120,
                heartbeat_interval_seconds=15,
                balance_snapshot_interval_seconds=30,
            )

            self.assertEqual("unit_observation.yml", result.script_config_name)
            self.assertEqual(str(Path(tmp) / "hummingbot" / "data" / "unit_events.jsonl"), result.install_targets["event_log_host_path"])
            script_config = Path(result.artifacts["script_config"]).read_text(encoding="utf-8")
            self.assertIn('observation_min_runtime_seconds: "120"', script_config)
            self.assertIn('heartbeat_interval_seconds: "15"', script_config)
            self.assertIn('balance_snapshot_interval_seconds: "30"', script_config)

    def test_blocks_live_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_cli_direct_paper_handoff(
                manifest=_manifest(live=True),
                runtime_preflight=_runtime_preflight(),
                output_dir=Path(tmp) / "handoff",
                session_id="unit",
                hummingbot_root=Path(tmp) / "hummingbot",
                allow_warnings=False,
            )

            self.assertEqual("blocked", result.decision)
            self.assertTrue(any(alert.title == "Manifest live trading enabled" for alert in result.alerts))


def _manifest(*, live: bool) -> dict[str, object]:
    return {
        "strategy_id": "unit_strategy",
        "connector_name": "binance_paper_trade",
        "live_trading_enabled": live,
        "orders": [
            {
                "client_order_id": "order-1",
                "trading_pair": "BTC-USDT",
                "side": "buy",
                "amount": "0.01",
                "price": "50000",
                "notional_quote": "500",
                "expected_fee_quote": "0.5",
                "source_intent_id": "intent-1",
            }
        ],
    }


def _runtime_preflight() -> dict[str, object]:
    return {
        "decision": "runtime_ready",
        "paper_trade_connectors": ["binance_paper_trade"],
    }
