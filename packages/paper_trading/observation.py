"""Paper trading observation loop and reports."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from time import sleep as default_sleep

from packages.backtesting.result import decimal_to_str
from packages.core.models import utc_now
from packages.paper_trading.cycle import PaperCycleResult, PaperTradingCycle


ObservationRecord = dict[str, object]


@dataclass(frozen=True, slots=True)
class PaperObservationSummary:
    status: str
    cycles: int
    ok_cycles: int
    failed_cycles: int
    routed_orders: int
    approved_orders: int
    rejected_orders: int
    market_data_incomplete_cycles: int
    first_equity: Decimal | None
    last_equity: Decimal | None
    min_equity: Decimal | None
    max_drawdown: Decimal
    ledger_path: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "cycles": self.cycles,
            "ok_cycles": self.ok_cycles,
            "failed_cycles": self.failed_cycles,
            "routed_orders": self.routed_orders,
            "approved_orders": self.approved_orders,
            "rejected_orders": self.rejected_orders,
            "market_data_incomplete_cycles": self.market_data_incomplete_cycles,
            "first_equity": _optional_decimal_to_str(self.first_equity),
            "last_equity": _optional_decimal_to_str(self.last_equity),
            "min_equity": _optional_decimal_to_str(self.min_equity),
            "max_drawdown": decimal_to_str(self.max_drawdown),
            "ledger_path": self.ledger_path,
        }


class PaperObservationLoop:
    def __init__(
        self,
        *,
        cycle_factory: Callable[[], PaperTradingCycle],
        observation_log: str | Path,
        summary_json: str | Path,
        report_md: str | Path,
        cycles: int | None,
        interval_seconds: Decimal,
        max_runtime_seconds: Decimal | None = None,
        pre_cycle_hook: Callable[[], dict[str, object] | None] | None = None,
        sleep_fn: Callable[[float], None] = default_sleep,
        now_fn: Callable[[], datetime] = utc_now,
    ) -> None:
        if cycles is not None and cycles <= 0:
            raise ValueError("cycles must be positive")
        if max_runtime_seconds is not None and max_runtime_seconds <= Decimal("0"):
            raise ValueError("max_runtime_seconds must be positive")
        if interval_seconds < Decimal("0"):
            raise ValueError("interval_seconds cannot be negative")
        if cycles is None and max_runtime_seconds is None:
            raise ValueError("cycles or max_runtime_seconds is required")

        self._cycle_factory = cycle_factory
        self._observation_log = Path(observation_log)
        self._summary_json = Path(summary_json)
        self._report_md = Path(report_md)
        self._cycles = cycles
        self._interval_seconds = interval_seconds
        self._max_runtime_seconds = max_runtime_seconds
        self._pre_cycle_hook = pre_cycle_hook
        self._sleep_fn = sleep_fn
        self._now_fn = now_fn

    def run(self) -> PaperObservationSummary:
        loop_started_at = self._now_fn()
        cycle_number = 0
        summary = summarize_observations(load_observations(self._observation_log))
        while self._should_start_next_cycle(
            cycle_number=cycle_number,
            loop_started_at=loop_started_at,
        ):
            cycle_number += 1
            record = self._run_one_cycle(cycle_number)
            append_observation(self._observation_log, record)
            records = load_observations(self._observation_log)
            summary = summarize_observations(records)
            write_observation_outputs(
                records=records,
                summary=summary,
                summary_json=self._summary_json,
                report_md=self._report_md,
            )

            if not self._should_start_next_cycle(
                cycle_number=cycle_number,
                loop_started_at=loop_started_at,
            ):
                break
            if self._interval_seconds > Decimal("0"):
                self._sleep_fn(float(self._interval_seconds))

        return summary

    def _run_one_cycle(self, cycle_number: int) -> ObservationRecord:
        started_at = self._now_fn()
        pre_cycle_payload = None
        try:
            if self._pre_cycle_hook is not None:
                pre_cycle_payload = self._pre_cycle_hook()
            result = self._cycle_factory().run_once()
        except Exception as exc:  # pragma: no cover - exercised by callers in production
            completed_at = self._now_fn()
            return observation_from_error(
                cycle_number=cycle_number,
                started_at=started_at,
                completed_at=completed_at,
                error=str(exc),
                pre_cycle=pre_cycle_payload,
            )
        completed_at = self._now_fn()
        return observation_from_result(
            cycle_number=cycle_number,
            started_at=started_at,
            completed_at=completed_at,
            result=result,
            pre_cycle=pre_cycle_payload,
        )

    def _should_start_next_cycle(
        self,
        *,
        cycle_number: int,
        loop_started_at: datetime,
    ) -> bool:
        if self._cycles is not None and cycle_number >= self._cycles:
            return False
        if self._max_runtime_seconds is None:
            return True
        elapsed = Decimal(str((self._now_fn() - loop_started_at).total_seconds()))
        return elapsed < self._max_runtime_seconds


def observation_from_result(
    *,
    cycle_number: int,
    started_at: datetime,
    completed_at: datetime,
    result: PaperCycleResult,
    pre_cycle: dict[str, object] | None = None,
) -> ObservationRecord:
    result_payload = result.to_dict()
    routed_orders = result_payload["routed_orders"]
    if not isinstance(routed_orders, list):
        raise TypeError("routed_orders must be a list")
    approved_orders = sum(1 for order in routed_orders if order["risk_status"] == "approved")
    market_data = result_payload["market_data"]
    if not isinstance(market_data, dict):
        raise TypeError("market_data must be a mapping")
    incomplete_count = sum(
        1
        for item in market_data.values()
        if isinstance(item, dict)
        and (not item.get("complete") or not item.get("quality_ok"))
    )
    return {
        "cycle_number": cycle_number,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": _duration_seconds(started_at, completed_at),
        "status": "ok",
        "strategy_id": result.strategy_id,
        "account": result_payload["account"],
        "target_weights": result_payload["target_weights"],
        "routed_orders": routed_orders,
        "routed_order_count": len(routed_orders),
        "approved_order_count": approved_orders,
        "rejected_order_count": len(routed_orders) - approved_orders,
        "market_data": market_data,
        "market_data_complete": incomplete_count == 0,
        "market_data_incomplete_count": incomplete_count,
        "pre_cycle": pre_cycle,
        "ledger_path": result.ledger_path,
    }


def observation_from_error(
    *,
    cycle_number: int,
    started_at: datetime,
    completed_at: datetime,
    error: str,
    pre_cycle: dict[str, object] | None = None,
) -> ObservationRecord:
    return {
        "cycle_number": cycle_number,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": _duration_seconds(started_at, completed_at),
        "status": "failed",
        "error": error,
        "routed_order_count": 0,
        "approved_order_count": 0,
        "rejected_order_count": 0,
        "market_data_complete": False,
        "market_data_incomplete_count": 0,
        "pre_cycle": pre_cycle,
        "ledger_path": None,
    }


def append_observation(path: str | Path, record: ObservationRecord) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, sort_keys=True))
        file.write("\n")


def load_observations(path: str | Path) -> tuple[ObservationRecord, ...]:
    input_path = Path(path)
    if not input_path.exists():
        return ()
    records = []
    with input_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return tuple(records)


def summarize_observations(records: tuple[ObservationRecord, ...]) -> PaperObservationSummary:
    ok_records = [record for record in records if record.get("status") == "ok"]
    failed_cycles = len(records) - len(ok_records)
    equities = [_record_equity(record) for record in ok_records]
    first_equity = equities[0] if equities else None
    last_equity = equities[-1] if equities else None
    min_equity = min(equities) if equities else None
    max_drawdown = _max_drawdown(equities)
    incomplete_cycles = sum(
        1
        for record in ok_records
        if not bool(record.get("market_data_complete", False))
    )
    rejected_orders = sum(_record_int(record, "rejected_order_count") for record in records)
    status = "ok"
    if failed_cycles or incomplete_cycles or rejected_orders:
        status = "attention_required"
    if not records:
        status = "empty"

    return PaperObservationSummary(
        status=status,
        cycles=len(records),
        ok_cycles=len(ok_records),
        failed_cycles=failed_cycles,
        routed_orders=sum(_record_int(record, "routed_order_count") for record in records),
        approved_orders=sum(_record_int(record, "approved_order_count") for record in records),
        rejected_orders=rejected_orders,
        market_data_incomplete_cycles=incomplete_cycles,
        first_equity=first_equity,
        last_equity=last_equity,
        min_equity=min_equity,
        max_drawdown=max_drawdown,
        ledger_path=_last_ledger_path(records),
    )


def write_observation_outputs(
    *,
    records: tuple[ObservationRecord, ...],
    summary: PaperObservationSummary,
    summary_json: str | Path,
    report_md: str | Path,
) -> None:
    summary_path = Path(summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = Path(report_md)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_observation_report(summary, records), encoding="utf-8")


def render_observation_report(
    summary: PaperObservationSummary,
    records: tuple[ObservationRecord, ...],
) -> str:
    lines = [
        "# Paper Observation Report",
        "",
        f"- status: `{summary.status}`",
        f"- cycles: `{summary.cycles}`",
        f"- ok cycles: `{summary.ok_cycles}`",
        f"- failed cycles: `{summary.failed_cycles}`",
        f"- routed orders: `{summary.routed_orders}`",
        f"- approved orders: `{summary.approved_orders}`",
        f"- rejected orders: `{summary.rejected_orders}`",
        f"- market data incomplete cycles: `{summary.market_data_incomplete_cycles}`",
        f"- first equity: `{_optional_decimal_to_str(summary.first_equity)}`",
        f"- last equity: `{_optional_decimal_to_str(summary.last_equity)}`",
        f"- min equity: `{_optional_decimal_to_str(summary.min_equity)}`",
        f"- max drawdown: `{decimal_to_str(summary.max_drawdown)}`",
        f"- ledger: `{summary.ledger_path}`",
        "",
        "## Recent Cycles",
        "",
        "| cycle | status | equity | routed | approved | rejected | data ok | refresh | error |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records[-10:]:
        lines.append(
            "| {cycle} | {status} | {equity} | {routed} | {approved} | {rejected} | {data_ok} | {refresh} | {error} |".format(
                cycle=record.get("cycle_number"),
                status=record.get("status"),
                equity=_record_equity_str(record),
                routed=record.get("routed_order_count", 0),
                approved=record.get("approved_order_count", 0),
                rejected=record.get("rejected_order_count", 0),
                data_ok=record.get("market_data_complete", False),
                refresh=_record_refresh_status(record),
                error=str(record.get("error", "")),
            )
        )
    lines.append("")
    return "\n".join(lines)


def _duration_seconds(started_at: datetime, completed_at: datetime) -> str:
    return f"{(completed_at - started_at).total_seconds():.6f}"


def _record_equity(record: ObservationRecord) -> Decimal:
    account = record.get("account", {})
    if not isinstance(account, dict):
        return Decimal("0")
    return Decimal(str(account.get("equity", "0")))


def _record_equity_str(record: ObservationRecord) -> str:
    if record.get("status") != "ok":
        return ""
    return decimal_to_str(_record_equity(record))


def _record_int(record: ObservationRecord, key: str) -> int:
    return int(str(record.get(key, 0)))


def _record_refresh_status(record: ObservationRecord) -> str:
    pre_cycle = record.get("pre_cycle")
    if not isinstance(pre_cycle, dict):
        return ""
    refresh_results = pre_cycle.get("market_data_refresh")
    if not isinstance(refresh_results, list):
        return ""
    statuses = sorted(
        {
            str(result.get("status"))
            for result in refresh_results
            if isinstance(result, dict)
        }
    )
    return ",".join(statuses)


def _last_ledger_path(records: tuple[ObservationRecord, ...]) -> str | None:
    for record in reversed(records):
        ledger_path = record.get("ledger_path")
        if ledger_path:
            return str(ledger_path)
    return None


def _max_drawdown(equities: list[Decimal]) -> Decimal:
    if not equities:
        return Decimal("0")
    peak = equities[0]
    max_drawdown = Decimal("0")
    for equity in equities:
        if equity > peak:
            peak = equity
        if peak > Decimal("0"):
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown


def _optional_decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return decimal_to_str(value)
