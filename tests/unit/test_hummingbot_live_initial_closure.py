from unittest import TestCase

from packages.adapters.hummingbot.live_initial_closure import build_initial_closure_report


class HummingbotLiveInitialClosureTest(TestCase):
    def test_closes_initial_flow_but_blocks_next_live_while_cooldown_active(self) -> None:
        report = build_initial_closure_report(
            post_trade_report=_post_trade_report(),
            cooldown_review=_cooldown_review(cooldown_elapsed=False),
            session_id="phase_6_9",
        )

        self.assertEqual("initial_v0_flow_closed_with_warnings", report.status)
        self.assertTrue(report.closure_summary["initial_flow_closed"])
        self.assertEqual("NO_GO_COOLDOWN_ACTIVE", report.next_live_decision["decision"])
        self.assertEqual("HOLD_UNDER_OBSERVATION", report.position_lifecycle_plan["stance"])
        self.assertTrue(report.position_lifecycle_plan["exit_requires_activation"])

    def test_allows_operator_review_after_cooldown(self) -> None:
        report = build_initial_closure_report(
            post_trade_report=_post_trade_report(),
            cooldown_review=_cooldown_review(cooldown_elapsed=True),
            session_id="phase_6_9",
        )

        self.assertEqual("initial_v0_flow_closed_with_warnings", report.status)
        self.assertEqual("GO_FOR_OPERATOR_REVIEW_ONLY", report.next_live_decision["decision"])


def _post_trade_report() -> dict[str, object]:
    return {
        "status": "live_post_trade_reconciled_with_warnings",
        "strategy_id": "crypto_relative_strength_v1",
        "account_id": "binance-main-spot",
        "order_checks": {
            "submitted_orders": 1,
            "filled_orders": 1,
            "db_fills": 1,
            "missing_submissions": [],
            "missing_fills": [],
            "missing_db_fills": [],
        },
        "fill_summary": {
            "average_price_quote": "76979.5",
            "cost_basis_quote_estimate": "49.266880",
            "fee_amount": "0.00000064",
            "fee_asset": "BTC",
            "gross_base_quantity": "0.00064",
            "gross_quote_notional": "49.266880",
            "net_base_quantity": "0.00063936",
            "fills": [{"trading_pair": "BTC-USDT", "side": "buy"}],
        },
        "balance_checks": {
            "status": "checked",
            "mismatches": [],
            "ending_balances": {"BTC": "0.00074442"},
        },
        "risk_checks": {
            "total_notional_inside_cap": True,
            "order_count_inside_cap": True,
            "price_deviation_inside_cap": True,
        },
    }


def _cooldown_review(*, cooldown_elapsed: bool) -> dict[str, object]:
    return {
        "cooldown_window": {
            "cooldown_elapsed": cooldown_elapsed,
            "next_review_not_before": "2026-04-29T02:34:33.175500+00:00",
        },
        "manual_checks": {"open_orders_check_status": "confirmed_clean"},
        "operational_checks": {"runner_config_armed": False},
        "expansion_controls": {
            "expansion_allowed": False,
            "allowed_pairs": ["BTC-USDT", "ETH-USDT"],
            "max_batch_notional": "50",
            "max_order_notional": "50",
        },
    }
