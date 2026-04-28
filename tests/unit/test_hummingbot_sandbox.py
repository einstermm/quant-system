from unittest import TestCase

from packages.adapters.hummingbot.sandbox import prepare_hummingbot_sandbox


class HummingbotSandboxTest(TestCase):
    def test_prepares_manifest_with_warning_gate_allowed(self) -> None:
        result = prepare_hummingbot_sandbox(
            review_payload=_review_payload(decision="sandbox_ready_with_warnings"),
            ledger_records=_ledger_records(),
            connector_name="binance_paper_trade",
            controller_name="unit_controller",
            allow_warnings=True,
        )

        self.assertEqual("sandbox_prepared_with_warnings", result.decision)
        self.assertFalse(result.manifest["live_trading_enabled"])
        self.assertEqual(2, len(result.manifest["controller_configs"]))
        self.assertEqual(2, len(result.manifest["orders"]))
        self.assertEqual("500", result.manifest["total_notional"])
        self.assertEqual(2, result.lifecycle["checks"]["submitted_orders"])
        self.assertEqual(2, result.lifecycle["checks"]["terminal_orders"])
        self.assertEqual(0, result.lifecycle["checks"]["duplicate_client_ids"])
        self.assertTrue(any(alert["severity"] == "WARN" for alert in result.alerts))

    def test_blocks_when_warning_gate_is_not_allowed(self) -> None:
        result = prepare_hummingbot_sandbox(
            review_payload=_review_payload(decision="sandbox_ready_with_warnings"),
            ledger_records=_ledger_records(),
            connector_name="binance_paper_trade",
            controller_name="unit_controller",
            allow_warnings=False,
        )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert["severity"] == "CRITICAL" for alert in result.alerts))

    def test_blocks_when_source_review_is_blocked(self) -> None:
        result = prepare_hummingbot_sandbox(
            review_payload=_review_payload(decision="blocked"),
            ledger_records=_ledger_records(),
            connector_name="binance_paper_trade",
            controller_name="unit_controller",
            allow_warnings=True,
        )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert["title"] == "Source review blocked" for alert in result.alerts))


def _review_payload(*, decision: str) -> dict[str, object]:
    return {
        "strategy_id": "unit_strategy",
        "account_id": "paper-main",
        "generated_at": "2026-04-27T00:00:00+00:00",
        "decision": decision,
        "trading": {
            "final_target_weights": {"BTC-USDT": "0.25", "XRP-USDT": "0.25"},
            "final_positions": [],
        },
    }


def _ledger_records() -> tuple[dict[str, object], ...]:
    return (
        {
            "paper_order_id": "paper-order-1",
            "intent_id": "intent-1",
            "account_id": "paper-main",
            "strategy_id": "unit_strategy",
            "symbol": "BTC-USDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
            "fill_price": "25000",
            "notional": "250",
            "fee": "0.25",
            "status": "filled",
            "created_at": "2026-04-27T00:00:00+00:00",
        },
        {
            "paper_order_id": "paper-order-2",
            "intent_id": "intent-2",
            "account_id": "paper-main",
            "strategy_id": "unit_strategy",
            "symbol": "XRP-USDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "100",
            "fill_price": "2.5",
            "notional": "250",
            "fee": "0.25",
            "status": "filled",
            "created_at": "2026-04-27T00:01:00+00:00",
        },
    )
