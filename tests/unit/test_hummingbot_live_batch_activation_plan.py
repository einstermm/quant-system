from decimal import Decimal
from unittest import TestCase

from packages.adapters.hummingbot.live_batch_activation_plan import (
    build_live_batch_activation_plan,
)


class HummingbotLiveBatchActivationPlanTest(TestCase):
    def test_plan_is_ready_but_pending_final_operator_go(self) -> None:
        report = build_live_batch_activation_plan(
            live_connector_preflight=_preflight(),
            credential_allowlist=_credential_allowlist(),
            operator_signoff=_operator_signoff(),
            live_risk_config=_risk_config(),
            environment=_environment(),
            session_id="unit",
            strategy_id="crypto_relative_strength_v1",
            batch_id="batch-1",
            allowed_pairs=("BTC-USDT", "ETH-USDT"),
            max_batch_orders=2,
            max_batch_notional=Decimal("500"),
        )

        self.assertEqual("live_batch_activation_plan_ready_pending_operator_go", report.decision)
        self.assertTrue(any(item.status == "MANUAL_REQUIRED" for item in report.checklist))
        self.assertFalse(report.batch_scope["live_order_submission_armed"])

    def test_plan_can_be_approved_after_explicit_final_go(self) -> None:
        report = build_live_batch_activation_plan(
            live_connector_preflight=_preflight(),
            credential_allowlist=_credential_allowlist(),
            operator_signoff=_operator_signoff(),
            live_risk_config=_risk_config(),
            environment=_environment(),
            session_id="unit",
            strategy_id="crypto_relative_strength_v1",
            batch_id="batch-1",
            allowed_pairs=("BTC-USDT", "ETH-USDT"),
            max_batch_orders=2,
            max_batch_notional=Decimal("500"),
            final_operator_go=True,
        )

        self.assertEqual("live_batch_activation_plan_approved", report.decision)

    def test_blocks_when_live_trading_is_already_enabled(self) -> None:
        report = build_live_batch_activation_plan(
            live_connector_preflight=_preflight(),
            credential_allowlist=_credential_allowlist(),
            operator_signoff=_operator_signoff(),
            live_risk_config=_risk_config(),
            environment=_environment(live_trading_enabled=True),
            session_id="unit",
            strategy_id="crypto_relative_strength_v1",
            batch_id="batch-1",
            allowed_pairs=("BTC-USDT", "ETH-USDT"),
            max_batch_orders=2,
            max_batch_notional=Decimal("500"),
        )

        self.assertEqual("live_batch_activation_plan_blocked", report.decision)
        self.assertTrue(any(item.item_id == "live_disabled" for item in report.checklist))

    def test_blocks_when_batch_notional_exceeds_gross_cap(self) -> None:
        report = build_live_batch_activation_plan(
            live_connector_preflight=_preflight(),
            credential_allowlist=_credential_allowlist(),
            operator_signoff=_operator_signoff(),
            live_risk_config=_risk_config(),
            environment=_environment(),
            session_id="unit",
            strategy_id="crypto_relative_strength_v1",
            batch_id="batch-1",
            allowed_pairs=("BTC-USDT", "ETH-USDT"),
            max_batch_orders=2,
            max_batch_notional=Decimal("1500"),
        )

        self.assertEqual("live_batch_activation_plan_blocked", report.decision)
        self.assertTrue(any(item.item_id == "batch_notional_cap" for item in report.checklist))


def _preflight() -> dict[str, object]:
    return {
        "decision": "live_connector_preflight_ready",
        "expected_connector": "binance",
        "market_type": "spot",
        "allowed_pairs": ["BTC-USDT", "ETH-USDT"],
        "connector_status": {
            "expected_host_config_path": "/tmp/hummingbot/conf/connectors/binance.yml",
        },
    }


def _credential_allowlist() -> dict[str, object]:
    return {
        "first_live_allowlist": {
            "trading_pairs": ["BTC-USDT", "ETH-USDT"],
        },
    }


def _operator_signoff() -> dict[str, object]:
    return {
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
