import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.adapters.hummingbot.sandbox_reconciliation import (
    SandboxReconciliationThresholds,
    SandboxRuntimeEvent,
    build_sandbox_reconciliation,
    load_event_jsonl,
    normalize_sandbox_events,
    replay_sandbox_events_from_manifest,
    write_events_jsonl,
    write_reconciliation_json,
    write_reconciliation_markdown,
)


class HummingbotSandboxReconciliationTest(TestCase):
    def test_reconciles_manifest_replay(self) -> None:
        manifest = _manifest()
        events = replay_sandbox_events_from_manifest(
            manifest=manifest,
            starting_quote_balance=Decimal("1000"),
        )

        result = build_sandbox_reconciliation(
            manifest=manifest,
            events=events,
            starting_quote_balance=Decimal("1000"),
        )

        self.assertEqual("sandbox_reconciled", result.decision)
        self.assertEqual(2, result.order_checks["submitted_orders"])
        self.assertEqual(2, result.order_checks["terminal_orders"])
        self.assertEqual(2, result.order_checks["filled_orders"])
        self.assertEqual(0, result.order_checks["disconnect_events"])
        self.assertEqual([], result.fill_checks["amount_mismatches"])
        self.assertEqual([], result.balance_checks["balance_mismatches"])
        self.assertEqual("499.50", result.balance_checks["expected_balances"]["USDT"])

    def test_blocks_when_terminal_event_is_missing(self) -> None:
        manifest = _manifest()
        events = (
            SandboxRuntimeEvent(
                event_id="order-1:submitted",
                event_type="submitted",
                created_at=_created_at(),
                client_order_id="order-1",
                trading_pair="BTC-USDT",
                side="buy",
            ),
        )

        result = build_sandbox_reconciliation(
            manifest=manifest,
            events=events,
            starting_quote_balance=None,
            thresholds=SandboxReconciliationThresholds(require_balance_event=False),
        )

        self.assertEqual("blocked", result.decision)
        self.assertTrue(any(alert.title == "Terminal mismatch" for alert in result.alerts))

    def test_blocks_unknown_order_id_and_balance_mismatch(self) -> None:
        manifest = _manifest()
        events = list(
            replay_sandbox_events_from_manifest(
                manifest=manifest,
                starting_quote_balance=Decimal("1000"),
            )
        )
        events.append(
            SandboxRuntimeEvent(
                event_id="unknown:submitted",
                event_type="submitted",
                created_at=_created_at(),
                client_order_id="unknown",
                trading_pair="ETH-USDT",
            )
        )
        events.append(
            SandboxRuntimeEvent(
                event_id="balance:USDT:bad",
                event_type="balance",
                created_at=_created_at(),
                balance_asset="USDT",
                balance_total=Decimal("1"),
            )
        )

        result = build_sandbox_reconciliation(
            manifest=manifest,
            events=tuple(events),
            starting_quote_balance=Decimal("1000"),
        )

        self.assertEqual("blocked", result.decision)
        self.assertEqual(["unknown"], result.order_checks["unknown_client_order_ids"])
        self.assertTrue(result.balance_checks["balance_mismatches"])

    def test_reconciles_runtime_submitted_amount_with_warning(self) -> None:
        manifest = _manifest()
        events = (
            SandboxRuntimeEvent(
                event_id="order-2:submitted",
                event_type="submitted",
                created_at=_created_at(),
                client_order_id="order-2",
                trading_pair="XRP-USDT",
                side="sell",
                raw={
                    "submitted_amount": "99.8",
                    "amount_adjustment_reason": "paper_available_balance_cap",
                },
            ),
            SandboxRuntimeEvent(
                event_id="order-2:filled",
                event_type="filled",
                created_at=_created_at(),
                client_order_id="order-2",
                trading_pair="XRP-USDT",
                side="sell",
                filled_amount=Decimal("99.8"),
                average_fill_price=Decimal("2.5"),
                fee_quote=Decimal("0.25"),
                raw={
                    "submitted_amount": "99.8",
                    "amount_adjustment_reason": "paper_available_balance_cap",
                },
            ),
        )
        manifest = {**manifest, "orders": [manifest["orders"][1]]}

        result = build_sandbox_reconciliation(
            manifest=manifest,
            events=events,
            starting_quote_balance=None,
            thresholds=SandboxReconciliationThresholds(require_balance_event=False),
        )

        self.assertEqual("sandbox_reconciled_with_warnings", result.decision)
        self.assertEqual([], result.fill_checks["amount_mismatches"])
        self.assertEqual(1, len(result.fill_checks["submitted_amount_adjustments"]))
        self.assertTrue(any(alert.title == "Submitted amount adjusted" for alert in result.alerts))

    def test_loads_and_writes_event_and_report_outputs(self) -> None:
        manifest = _manifest()
        events = replay_sandbox_events_from_manifest(
            manifest=manifest,
            starting_quote_balance=Decimal("1000"),
        )
        result = build_sandbox_reconciliation(
            manifest=manifest,
            events=events,
            starting_quote_balance=Decimal("1000"),
        )

        with TemporaryDirectory() as directory:
            events_path = write_events_jsonl(events, Path(directory) / "events.jsonl")
            json_path = write_reconciliation_json(result, Path(directory) / "reconciliation.json")
            md_path = write_reconciliation_markdown(result, Path(directory) / "reconciliation.md")
            loaded = load_event_jsonl(events_path)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = md_path.read_text(encoding="utf-8")

        self.assertEqual(len(events), len(loaded))
        self.assertEqual("sandbox_reconciled", payload["decision"])
        self.assertIn("Hummingbot Sandbox Reconciliation", markdown)

    def test_expands_balance_snapshot_payload(self) -> None:
        events = normalize_sandbox_events(
            {
                "event_type": "balance_snapshot",
                "created_at": "2026-04-27T00:00:00+00:00",
                "balances": {
                    "USDT": {"total": "1000"},
                    "BTC": "0.01",
                },
            }
        )

        self.assertEqual(2, len(events))
        self.assertEqual({"BTC", "USDT"}, {str(event.balance_asset) for event in events})


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "hummingbot_sandbox_manifest_v1",
        "strategy_id": "unit_strategy",
        "account_id": "paper-main",
        "connector_name": "binance_paper_trade",
        "controller_name": "unit_controller",
        "live_trading_enabled": False,
        "source_review_generated_at": "2026-04-27T00:00:00+00:00",
        "total_notional": "500",
        "orders": [
            {
                "client_order_id": "order-1",
                "trading_pair": "BTC-USDT",
                "side": "buy",
                "amount": "0.01",
                "price": "25000",
                "notional_quote": "250",
                "expected_fee_quote": "0.25",
            },
            {
                "client_order_id": "order-2",
                "trading_pair": "XRP-USDT",
                "side": "buy",
                "amount": "100",
                "price": "2.5",
                "notional_quote": "250",
                "expected_fee_quote": "0.25",
            },
        ],
    }


def _created_at():
    return replay_sandbox_events_from_manifest(manifest=_manifest())[0].created_at
