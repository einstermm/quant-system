from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.live_connector_preflight import build_live_connector_preflight


class HummingbotLiveConnectorPreflightTest(TestCase):
    def test_pending_when_expected_connector_is_not_configured(self) -> None:
        with TemporaryDirectory() as tmp:
            report = build_live_connector_preflight(
                activation_checklist=_activation(),
                credential_allowlist=_credential_allowlist(),
                operator_signoff=_operator_signoff(),
                live_risk_config=_risk_config(),
                environment=_environment(),
                hummingbot_root=Path(tmp),
                session_id="unit",
                strategy_id="crypto_relative_strength_v1",
                expected_connector="binance",
                market_type="spot",
                allowed_pairs=("BTC-USDT", "ETH-USDT"),
                required_secret_fields=("binance_api_key", "binance_api_secret"),
            )

            self.assertEqual("live_connector_config_pending", report.decision)
            self.assertTrue(
                any(
                    item.item_id == "expected_connector_config" and item.status == "PENDING"
                    for item in report.checklist
                )
            )
            self.assertTrue(report.connector_status["secret_values_redacted"])

    def test_ready_when_expected_connector_config_is_present(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            connector = root / "conf" / "connectors" / "binance.yml"
            connector.parent.mkdir(parents=True)
            connector.write_text(
                "binance_api_key: should-not-leak\n"
                "binance_api_secret: should-not-leak-either\n",
                encoding="utf-8",
            )

            report = build_live_connector_preflight(
                activation_checklist=_activation(),
                credential_allowlist=_credential_allowlist(),
                operator_signoff=_operator_signoff(),
                live_risk_config=_risk_config(),
                environment=_environment(),
                hummingbot_root=root,
                session_id="unit",
                strategy_id="crypto_relative_strength_v1",
                expected_connector="binance",
                market_type="spot",
                allowed_pairs=("BTC-USDT", "ETH-USDT"),
                required_secret_fields=("binance_api_key", "binance_api_secret"),
            )

            self.assertEqual("live_connector_preflight_ready", report.decision)
            payload = report.to_dict()
            self.assertNotIn("should-not-leak", str(payload))
            self.assertIn("binance_api_key", str(payload))

    def test_blocks_when_exchange_keys_are_in_quant_env(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            connector = root / "conf" / "connectors" / "binance.yml"
            connector.parent.mkdir(parents=True)
            connector.write_text(
                "binance_api_key: redacted\n"
                "binance_api_secret: redacted\n",
                encoding="utf-8",
            )

            report = build_live_connector_preflight(
                activation_checklist=_activation(),
                credential_allowlist=_credential_allowlist(),
                operator_signoff=_operator_signoff(),
                live_risk_config=_risk_config(),
                environment=_environment(exchange_key_env_detected=True),
                hummingbot_root=root,
                session_id="unit",
                strategy_id="crypto_relative_strength_v1",
                expected_connector="binance",
                market_type="spot",
                allowed_pairs=("BTC-USDT", "ETH-USDT"),
                required_secret_fields=("binance_api_key", "binance_api_secret"),
            )

            self.assertEqual("live_connector_preflight_blocked", report.decision)
            self.assertTrue(
                any(item.item_id == "exchange_keys_not_in_quant_env" for item in report.checklist)
            )


def _activation() -> dict[str, object]:
    return {
        "decision": "live_activation_ready",
    }


def _credential_allowlist() -> dict[str, object]:
    return {
        "decision": "credential_allowlist_review_confirmed",
        "accepted_live_risk_limits": {
            "max_order_notional": "250",
            "max_symbol_notional": "500",
            "max_gross_notional": "1000",
            "max_daily_loss": "50",
        },
        "first_live_allowlist": {
            "connector": "binance",
            "market_type": "spot",
            "trading_pairs": ["BTC-USDT", "ETH-USDT"],
        },
    }


def _operator_signoff() -> dict[str, object]:
    return {
        "decision": "operator_signoff_confirmed",
        "confirmed_limits": {
            "max_order_notional": "250",
            "max_symbol_notional": "500",
            "max_gross_notional": "1000",
            "max_daily_loss": "50",
            "max_drawdown_pct": "0.05",
        },
        "first_live_allowlist": ["BTC-USDT", "ETH-USDT"],
    }


def _risk_config() -> dict[str, object]:
    return {
        "max_order_notional": "250",
        "max_symbol_notional": "500",
        "max_gross_notional": "1000",
        "max_daily_loss": "50",
        "max_drawdown_pct": "0.05",
    }


def _environment(**overrides: object) -> dict[str, object]:
    environment = {
        "live_trading_enabled": False,
        "global_kill_switch": True,
        "alert_channel_configured": True,
        "exchange_key_env_detected": False,
    }
    environment.update(overrides)
    return environment
