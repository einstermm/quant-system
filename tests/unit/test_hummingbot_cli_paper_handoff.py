import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.cli_paper_handoff import build_cli_paper_handoff


class HummingbotCliPaperHandoffTest(TestCase):
    def test_builds_cli_paper_files(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_cli_paper_handoff(
                manifest=_manifest(live=False),
                runtime_preflight=_runtime_preflight("runtime_ready"),
                output_dir=Path(tmp) / "handoff",
                session_id="unit-session",
                hummingbot_root=Path(tmp) / "hummingbot",
                allow_warnings=False,
            )

            self.assertEqual("cli_paper_handoff_ready", result.decision)
            controller_source = Path(result.artifacts["controller_source"])
            script_config = Path(result.artifacts["script_config"])
            controller_config_dir = Path(result.artifacts["controller_config_dir"])

            self.assertTrue(controller_source.exists())
            self.assertIn("QuantSystemSandboxOrderController", controller_source.read_text(encoding="utf-8"))
            self.assertTrue(script_config.exists())
            self.assertIn("v2_with_controllers.py", script_config.read_text(encoding="utf-8"))
            configs = sorted(controller_config_dir.glob("*.yml"))
            self.assertEqual(2, len(configs))
            self.assertIn("binance_paper_trade", configs[0].read_text(encoding="utf-8"))
            self.assertIn("client_order_id", configs[0].read_text(encoding="utf-8"))

            payload = json.loads(Path(result.artifacts["handoff_json"]).read_text(encoding="utf-8"))
            self.assertEqual("unit_strategy", payload["summary"]["strategy_id"])

    def test_blocks_live_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_cli_paper_handoff(
                manifest=_manifest(live=True),
                runtime_preflight=_runtime_preflight("runtime_ready"),
                output_dir=Path(tmp) / "handoff",
                session_id="unit-session",
                hummingbot_root=Path(tmp) / "hummingbot",
                allow_warnings=False,
            )

            self.assertEqual("blocked", result.decision)
            self.assertTrue(any(alert.title == "Manifest live trading enabled" for alert in result.alerts))

    def test_blocks_missing_paper_connector(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_cli_paper_handoff(
                manifest=_manifest(live=False),
                runtime_preflight={"decision": "runtime_ready", "paper_trade_connectors": []},
                output_dir=Path(tmp) / "handoff",
                session_id="unit-session",
                hummingbot_root=Path(tmp) / "hummingbot",
                allow_warnings=False,
            )

            self.assertEqual("blocked", result.decision)
            self.assertTrue(any(alert.title == "Paper connector missing" for alert in result.alerts))


def _manifest(*, live: bool) -> dict[str, object]:
    return {
        "strategy_id": "unit_strategy",
        "connector_name": "binance_paper_trade",
        "live_trading_enabled": live,
        "orders": [
            {
                "client_order_id": "order-btc-1",
                "trading_pair": "BTC-USDT",
                "side": "buy",
                "order_type": "market",
                "amount": "0.01",
                "price": "50000",
                "notional_quote": "500",
                "expected_fee_quote": "0.5",
                "reduce_only": False,
                "source_intent_id": "intent-btc",
            },
            {
                "client_order_id": "order-eth-1",
                "trading_pair": "ETH-USDT",
                "side": "sell",
                "order_type": "market",
                "amount": "0.1",
                "price": "3000",
                "notional_quote": "300",
                "expected_fee_quote": "0.3",
                "reduce_only": True,
                "source_intent_id": "intent-eth",
            },
        ],
    }


def _runtime_preflight(decision: str) -> dict[str, object]:
    return {
        "decision": decision,
        "paper_trade_connectors": ["binance_paper_trade"],
    }
