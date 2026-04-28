import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from packages.reporting.paper_observation_review import (
    PaperObservationReviewThresholds,
    build_paper_observation_review,
    load_jsonl,
    write_review_json,
    write_review_markdown,
)


class PaperObservationReviewTest(TestCase):
    def test_builds_sandbox_ready_with_warnings_review(self) -> None:
        review = build_paper_observation_review(
            observation_records=_observation_records(),
            ledger_records=_ledger_records(),
            readiness_payload=_readiness_payload(status="paper_ready_with_warnings"),
            initial_equity=Decimal("2000"),
            thresholds=PaperObservationReviewThresholds(min_duration_hours=Decimal("23")),
        )

        self.assertEqual("sandbox_ready_with_warnings", review.decision)
        self.assertEqual("unit_strategy", review.strategy_id)
        self.assertEqual("paper-main", review.account_id)
        self.assertEqual(2, review.trading["filled_orders"])
        self.assertEqual("10", review.trading["net_pnl"])
        self.assertEqual("0.005", review.trading["net_return"])
        self.assertTrue(any(alert.title == "Prior readiness not clean" for alert in review.alerts))
        self.assertFalse(any(alert.severity == "CRITICAL" for alert in review.alerts))

    def test_blocks_when_cycle_failed(self) -> None:
        records = list(_observation_records())
        records[-1] = {
            **records[-1],
            "status": "failed",
            "error": "market data refresh failed",
            "market_data_complete": False,
        }

        review = build_paper_observation_review(
            observation_records=tuple(records),
            ledger_records=_ledger_records(),
            readiness_payload=_readiness_payload(status="paper_ready"),
            initial_equity=Decimal("2000"),
            thresholds=PaperObservationReviewThresholds(min_duration_hours=Decimal("23")),
        )

        self.assertEqual("blocked", review.decision)
        self.assertTrue(any(alert.title == "Failed paper cycles" for alert in review.alerts))

    def test_writes_review_outputs(self) -> None:
        review = build_paper_observation_review(
            observation_records=_observation_records(),
            ledger_records=_ledger_records(),
            readiness_payload=_readiness_payload(status="paper_ready"),
            initial_equity=Decimal("2000"),
            thresholds=PaperObservationReviewThresholds(min_duration_hours=Decimal("23")),
        )

        with TemporaryDirectory() as directory:
            json_path = write_review_json(review, Path(directory) / "review.json")
            md_path = write_review_markdown(review, Path(directory) / "review.md")
            jsonl_path = Path(directory) / "observation.jsonl"
            jsonl_path.write_text(
                "\n".join(json.dumps(record) for record in _observation_records()) + "\n",
                encoding="utf-8",
            )
            loaded = load_jsonl(jsonl_path)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = md_path.read_text(encoding="utf-8")

        self.assertEqual(review.decision, payload["decision"])
        self.assertEqual(2, len(loaded))
        self.assertIn("Paper Observation Review", markdown)


def _observation_records() -> tuple[dict[str, object], ...]:
    return (
        _record(
            cycle=1,
            started_at="2026-04-26T00:00:00+00:00",
            completed_at="2026-04-26T00:01:00+00:00",
            equity="1999",
            routed=2,
            approved=2,
        ),
        _record(
            cycle=2,
            started_at="2026-04-27T00:00:00+00:00",
            completed_at="2026-04-27T00:00:30+00:00",
            equity="2010",
            routed=0,
            approved=0,
        ),
    )


def _record(
    *,
    cycle: int,
    started_at: str,
    completed_at: str,
    equity: str,
    routed: int,
    approved: int,
) -> dict[str, object]:
    return {
        "cycle_number": cycle,
        "started_at": started_at,
        "completed_at": completed_at,
        "status": "ok",
        "strategy_id": "unit_strategy",
        "account": {
            "account_id": "paper-main",
            "equity": equity,
            "cash": "1500",
            "gross_exposure": "500",
            "positions": [
                {
                    "symbol": "BTC-USDT",
                    "quantity": "0.01",
                    "mark_price": "50000",
                    "notional": "500",
                }
            ],
        },
        "target_weights": {"BTC-USDT": "0.25"},
        "routed_order_count": routed,
        "approved_order_count": approved,
        "rejected_order_count": routed - approved,
        "routed_orders": [],
        "market_data_complete": True,
        "market_data_incomplete_count": 0,
        "pre_cycle": {
            "refresh_failed": False,
            "runtime_end": "2026-04-27T00:00:00+00:00",
            "market_data_refresh": [
                {
                    "status": "ok",
                    "trading_pair": "BTC-USDT",
                    "fetched_candles": 2,
                    "latest_after": "2026-04-26T20:00:00+00:00",
                }
            ],
        },
        "ledger_path": "paper.jsonl",
    }


def _ledger_records() -> tuple[dict[str, object], ...]:
    return (
        {
            "paper_order_id": "paper-1",
            "intent_id": "intent-1",
            "account_id": "paper-main",
            "strategy_id": "unit_strategy",
            "symbol": "BTC-USDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
            "fill_price": "50000",
            "notional": "500",
            "fee": "0.5",
            "status": "filled",
            "created_at": "2026-04-26T00:00:30+00:00",
        },
        {
            "paper_order_id": "paper-2",
            "intent_id": "intent-2",
            "account_id": "paper-main",
            "strategy_id": "unit_strategy",
            "symbol": "XRP-USDT",
            "side": "sell",
            "order_type": "market",
            "quantity": "100",
            "fill_price": "1",
            "notional": "100",
            "fee": "0.1",
            "status": "filled",
            "created_at": "2026-04-27T00:00:00+00:00",
        },
    )


def _readiness_payload(*, status: str) -> dict[str, object]:
    return {
        "status": status,
        "alerts": [
            {
                "severity": "WARN",
                "title": "Return concentration",
                "message": "Average return is heavily influenced by the best fold.",
            }
        ],
    }
