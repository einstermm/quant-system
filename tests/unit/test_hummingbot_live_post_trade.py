import json
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import TestCase

from packages.adapters.hummingbot.live_post_trade import (
    build_live_post_trade_report,
    write_trade_tax_csv,
)


class HummingbotLivePostTradeTest(TestCase):
    def test_reconciles_live_fill_with_base_asset_fee(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_jsonl = root / "events.jsonl"
            sqlite_db = root / "session.sqlite"
            log_file = root / "hbot.log"
            _write_event_jsonl(event_jsonl)
            _write_sqlite(sqlite_db)
            log_file.write_text(
                "Failed to connect MQTT Bridge\nHummingbot stopped.\n",
                encoding="utf-8",
            )

            report, fills = build_live_post_trade_report(
                event_jsonl=event_jsonl,
                sqlite_db=sqlite_db,
                log_file=log_file,
                candidate_package=_candidate_package(),
                runner_package=_runner_package(),
                session_id="phase_6_7",
                account_id="binance-main-spot",
                strategy_id="crypto_relative_strength_v1",
                cad_fx_rate=Decimal("1"),
                fx_source="validation_only_not_tax_filing",
                runner_container_status="Exited (0)",
            )

            self.assertEqual("live_post_trade_reconciled_with_warnings", report.status)
            self.assertEqual(1, report.order_checks["filled_orders"])
            self.assertEqual("49.266880", report.fill_summary["gross_quote_notional"])
            self.assertEqual("0.00063936", report.fill_summary["net_base_quantity"])
            self.assertEqual("0.049266880", report.fill_summary["fee_quote_estimate"])
            self.assertEqual("checked", report.balance_checks["status"])
            self.assertEqual([], report.balance_checks["mismatches"])
            self.assertTrue(report.risk_checks["total_notional_inside_cap"])
            self.assertTrue(report.risk_checks["price_deviation_inside_cap"])

            csv_path = write_trade_tax_csv(fills, root / "tax.csv")
            self.assertIn("fee_asset", csv_path.read_text(encoding="utf-8"))


def _write_event_jsonl(path: Path) -> None:
    records = [
        {
            "event_type": "session_started",
            "created_at": "2026-04-28T02:34:01+00:00",
            "client_order_id": "session",
        },
        {
            "event_type": "balance",
            "created_at": "2026-04-28T02:34:01.1+00:00",
            "balance_asset": "BTC",
            "balance_total": "0.00010506",
        },
        {
            "event_type": "balance",
            "created_at": "2026-04-28T02:34:01.1+00:00",
            "balance_asset": "USDT",
            "balance_total": "62.93633",
        },
        {
            "event_type": "submitted",
            "created_at": "2026-04-28T02:34:01.2+00:00",
            "client_order_id": "order-1",
            "hb_order_id": "hb-1",
            "trading_pair": "BTC-USDT",
        },
        {
            "event_type": "filled",
            "created_at": "2026-04-28T02:34:01.4+00:00",
            "client_order_id": "order-1",
            "hb_order_id": "hb-1",
            "trading_pair": "BTC-USDT",
        },
        {
            "event_type": "balance",
            "created_at": "2026-04-28T02:34:33+00:00",
            "balance_asset": "BTC",
            "balance_total": "0.00074442",
        },
        {
            "event_type": "balance",
            "created_at": "2026-04-28T02:34:33+00:00",
            "balance_asset": "USDT",
            "balance_total": "13.66945",
        },
        {
            "event_type": "session_completed",
            "created_at": "2026-04-28T02:34:33+00:00",
            "client_order_id": "session",
        },
    ]
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record))
            file.write("\n")


def _write_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            create table TradeFill (
              config_file_path text not null,
              strategy text not null,
              market text not null,
              symbol text not null,
              base_asset text not null,
              quote_asset text not null,
              timestamp bigint not null,
              order_id text not null,
              trade_type text not null,
              order_type text not null,
              price bigint not null,
              amount bigint not null,
              leverage integer not null,
              trade_fee json not null,
              trade_fee_in_quote bigint,
              exchange_trade_id text not null,
              position text
            );
            create table "Order" (
              id text primary key,
              exchange_order_id text,
              last_status text
            );
            """
        )
        connection.execute(
            """
            insert into TradeFill values (
              'config.yml', 'quant_system_live_one_batch', 'binance', 'BTC-USDT', 'BTC', 'USDT',
              1777343641000, 'hb-1', 'BUY', 'MARKET', 76979500000, 640, 1,
              '{"fee_type":"DeductedFromReturns","percent":"0","percent_token":"BTC",
                "flat_fees":[{"token":"BTC","amount":"6.4E-7"}]}',
              49266, '6256967929', 'NIL'
            )
            """
        )
        connection.execute(
            "insert into \"Order\" values ('hb-1', 'exchange-1', 'BuyOrderCompleted')"
        )
        connection.commit()
    finally:
        connection.close()


def _candidate_package() -> dict[str, object]:
    return {
        "candidate_orders": [
            {
                "client_order_id": "order-1",
                "trading_pair": "BTC-USDT",
                "estimated_price": "77371.32",
            }
        ]
    }


def _runner_package() -> dict[str, object]:
    return {
        "summary": {
            "max_batch_notional": "50",
            "max_order_notional": "50",
            "max_price_deviation_pct": "0.02",
            "allowed_pairs": ["BTC-USDT", "ETH-USDT"],
        }
    }
