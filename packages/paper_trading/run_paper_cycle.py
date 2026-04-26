"""Run one local paper trading cycle."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import load_backtest_config
from packages.data.market_data_service import MarketDataService
from packages.data.sqlite_candle_repository import SQLiteCandleRepository
from packages.paper_trading.cycle import PaperTradingCycle
from packages.paper_trading.ledger import PaperLedger
from packages.paper_trading.runtime import assert_readiness, load_kill_switch, load_risk_limits


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single local paper trading cycle.")
    parser.add_argument("--strategy-dir", required=True, help="Strategy directory")
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--readiness-json", required=True, help="Paper readiness JSON gate")
    parser.add_argument("--allow-readiness-warnings", action="store_true", help="Allow paper_ready_with_warnings")
    parser.add_argument("--ledger", required=True, help="Paper JSONL ledger path")
    parser.add_argument("--summary", required=True, help="Output cycle summary JSON")
    parser.add_argument("--account-id", default="paper-main", help="Paper account id")
    parser.add_argument("--initial-equity", default="2000", help="Initial paper equity")
    parser.add_argument("--kill-switch-file", help="Optional JSON kill switch state")
    args = parser.parse_args()

    assert_readiness(Path(args.readiness_json), allow_warnings=args.allow_readiness_warnings)
    strategy_dir = Path(args.strategy_dir)
    config = load_backtest_config(strategy_dir)
    risk_limits = load_risk_limits(strategy_dir / "risk.yml")
    kill_switch = load_kill_switch(Path(args.kill_switch_file) if args.kill_switch_file else None)
    ledger = PaperLedger(Path(args.ledger))

    with SQLiteCandleRepository(Path(args.db)) as repository:
        service = MarketDataService(repository)
        cycle = PaperTradingCycle(
            market_data_service=service,
            config=config,
            risk_limits=risk_limits,
            ledger=ledger,
            account_id=args.account_id,
            initial_equity=Decimal(args.initial_equity),
            kill_switch=kill_switch,
        )
        result = cycle.run_once()

    output_path = Path(args.summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    approved = sum(1 for order in result.routed_orders if order.risk_decision.approved)
    print(
        f"strategy={result.strategy_id} account={result.account.account_id} "
        f"orders={len(result.routed_orders)} approved={approved} "
        f"equity={result.account.equity} summary={output_path} ledger={ledger.path}"
    )


if __name__ == "__main__":
    main()
