from datetime import UTC, datetime
from decimal import Decimal
from unittest import TestCase

from packages.accounting.tax_export import (
    build_trade_tax_export_rows_from_hummingbot_events,
    build_trade_tax_export_summary,
)
from packages.adapters.hummingbot.sandbox_reconciliation import SandboxRuntimeEvent


class TaxExportTest(TestCase):
    def test_builds_trade_tax_export_rows_from_hummingbot_fills(self) -> None:
        rows = build_trade_tax_export_rows_from_hummingbot_events(
            events=(
                SandboxRuntimeEvent(
                    event_id="order-1:filled",
                    event_type="filled",
                    created_at=datetime(2026, 4, 27, tzinfo=UTC),
                    client_order_id="order-1",
                    trading_pair="BTC-USDT",
                    side="buy",
                    filled_amount=Decimal("0.01"),
                    average_fill_price=Decimal("50000"),
                    fee_quote=Decimal("0.5"),
                ),
                SandboxRuntimeEvent(
                    event_id="order-2:filled",
                    event_type="filled",
                    created_at=datetime(2026, 4, 27, tzinfo=UTC),
                    client_order_id="order-2",
                    trading_pair="BTC-USDT",
                    side="sell",
                    filled_amount=Decimal("0.005"),
                    average_fill_price=Decimal("60000"),
                    fee_quote=Decimal("0.3"),
                ),
            ),
            account_id="paper",
            strategy_id="strategy",
            cad_fx_rate=Decimal("1.35"),
            fx_source="unit_test",
        )

        self.assertEqual(2, len(rows))
        self.assertEqual("BTC", rows[0].base_asset)
        self.assertEqual(Decimal("500.5"), rows[0].cost_basis_quote)
        self.assertEqual(Decimal("299.7"), rows[1].proceeds_quote)

    def test_summary_warns_for_validation_fx_and_acb_matching(self) -> None:
        rows = build_trade_tax_export_rows_from_hummingbot_events(
            events=(
                SandboxRuntimeEvent(
                    event_id="order-1:filled",
                    event_type="filled",
                    created_at=datetime(2026, 4, 27, tzinfo=UTC),
                    client_order_id="order-1",
                    trading_pair="XRP-USDT",
                    side="sell",
                    filled_amount=Decimal("100"),
                    average_fill_price=Decimal("1"),
                    fee_quote=Decimal("0.1"),
                ),
            ),
            account_id="paper",
            strategy_id="strategy",
            cad_fx_rate=Decimal("1"),
            fx_source="validation_only",
        )
        summary = build_trade_tax_export_summary(
            rows=rows,
            strategy_id="strategy",
            account_id="paper",
            source="hummingbot_export",
            quote_asset="USDT",
            cad_fx_rate=Decimal("1"),
            fx_source="validation_only",
        )

        self.assertEqual("tax_export_ready_with_warnings", summary.status)
        self.assertTrue(any(alert.title == "ACB lot matching required" for alert in summary.alerts))
