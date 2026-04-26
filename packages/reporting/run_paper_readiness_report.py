"""Generate paper trading readiness reports from walk-forward outputs."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from packages.reporting.paper_readiness import (
    PaperReadinessThresholds,
    build_paper_readiness_report,
    load_json,
    write_report_json,
    write_report_markdown,
    write_risk_off_runbook,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a paper trading readiness report.")
    parser.add_argument("--walk-forward-json", required=True, help="Walk-forward JSON input")
    parser.add_argument("--capacity-stress-json", help="Optional high-equity stress backtest JSON")
    parser.add_argument("--output-json", required=True, help="Output readiness JSON")
    parser.add_argument("--output-md", required=True, help="Output readiness Markdown")
    parser.add_argument("--runbook-md", required=True, help="Output risk-off runbook Markdown")
    parser.add_argument("--min-capacity-equity", default="100000", help="Minimum required capacity equity")
    parser.add_argument("--max-worst-return-loss", default="0.05", help="Maximum allowed worst fold loss")
    parser.add_argument("--max-worst-drawdown", default="0.12", help="Maximum allowed worst fold drawdown")
    parser.add_argument("--max-worst-tail-loss", default="0.06", help="Maximum allowed worst fold tail loss")
    args = parser.parse_args()

    thresholds = PaperReadinessThresholds(
        min_capacity_equity=Decimal(args.min_capacity_equity),
        max_worst_return_loss=Decimal(args.max_worst_return_loss),
        max_worst_drawdown=Decimal(args.max_worst_drawdown),
        max_worst_tail_loss=Decimal(args.max_worst_tail_loss),
    )
    report = build_paper_readiness_report(
        walk_forward_payload=load_json(Path(args.walk_forward_json)),
        capacity_stress_payload=load_json(Path(args.capacity_stress_json))
        if args.capacity_stress_json
        else None,
        thresholds=thresholds,
    )
    json_path = write_report_json(report, Path(args.output_json))
    md_path = write_report_markdown(report, Path(args.output_md))
    runbook_path = write_risk_off_runbook(report, Path(args.runbook_md))
    print(
        f"strategy={report.strategy_id} status={report.status} "
        f"alerts={len(report.alerts)} output={json_path} markdown={md_path} runbook={runbook_path}"
    )


if __name__ == "__main__":
    main()
