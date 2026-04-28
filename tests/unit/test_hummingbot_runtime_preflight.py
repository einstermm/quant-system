import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.runtime_preflight import (
    build_runtime_preflight,
    parse_connector_config,
    write_runtime_preflight_json,
)


class HummingbotRuntimePreflightTest(TestCase):
    def test_blocks_live_connector_with_secret_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            connector_file = root / "bots" / "credentials" / "master_account" / "connectors" / "binance_perpetual.yml"
            connector_file.parent.mkdir(parents=True)
            connector_file.write_text(
                "connector: binance_perpetual\n"
                "binance_perpetual_api_key: should-not-leak\n"
                "binance_perpetual_api_secret: should-not-leak-either\n",
                encoding="utf-8",
            )

            result = build_runtime_preflight(
                scan_roots=[root / "bots"],
                session_id="unit",
                expected_connector="binance_paper_trade",
            )

            self.assertEqual("blocked", result.decision)
            self.assertTrue(any(alert.title == "Live connector config present" for alert in result.alerts))
            self.assertTrue(any(alert.title == "Live connector secret fields present" for alert in result.alerts))
            self.assertEqual("master_account", result.connector_configs[0].account_id)
            self.assertEqual("binance_perpetual", result.connector_configs[0].connector)

            output_json = root / "preflight.json"
            write_runtime_preflight_json(result, output_json)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertNotIn("should-not-leak", json.dumps(payload))
            self.assertIn("binance_perpetual_api_key", json.dumps(payload))

    def test_allows_expected_paper_connector(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            connector_file = root / "credentials" / "paper_account" / "connectors" / "binance_paper_trade.yml"
            connector_file.parent.mkdir(parents=True)
            connector_file.write_text(
                "connector: binance_paper_trade\n",
                encoding="utf-8",
            )

            result = build_runtime_preflight(
                scan_roots=[root],
                session_id="unit",
                expected_connector="binance_paper_trade",
            )

            self.assertEqual("runtime_ready", result.decision)
            self.assertFalse(any(alert.severity == "CRITICAL" for alert in result.alerts))

    def test_warns_when_no_connector_configs_exist(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_runtime_preflight(
                scan_roots=[Path(tmp)],
                session_id="unit",
                expected_connector="binance_paper_trade",
            )

            self.assertEqual("runtime_ready_with_warnings", result.decision)
            self.assertTrue(any(alert.title == "No paper or testnet connector config" for alert in result.alerts))

    def test_detects_paper_trade_connector_from_conf_client(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            conf_client = root / "credentials" / "paper_account" / "conf_client.yml"
            conf_client.parent.mkdir(parents=True)
            conf_client.write_text(
                "paper_trade:\n"
                "  paper_trade_exchanges:\n"
                "  - binance\n"
                "  - kucoin\n",
                encoding="utf-8",
            )

            result = build_runtime_preflight(
                scan_roots=[root],
                session_id="unit",
                expected_connector="binance_paper_trade",
            )

            self.assertEqual("runtime_ready", result.decision)
            self.assertIn("binance_paper_trade", result.paper_trade_connectors)
            self.assertFalse(any(alert.title == "Expected connector not configured" for alert in result.alerts))

    def test_parses_account_id_from_credentials_path(self) -> None:
        with TemporaryDirectory() as tmp:
            connector_file = Path(tmp) / "credentials" / "sandbox" / "connectors" / "mock_paper_exchange.yml"
            connector_file.parent.mkdir(parents=True)
            connector_file.write_text("connector: mock_paper_exchange\n", encoding="utf-8")

            finding = parse_connector_config(connector_file)

            self.assertEqual("sandbox", finding.account_id)
            self.assertEqual("paper", finding.connector_risk)
