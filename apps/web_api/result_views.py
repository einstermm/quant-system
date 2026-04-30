"""Structured result views for visualizing completed web jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Mapping

from apps.web_api.backtest_candidates import BACKTEST_CANDIDATE_PATH
from apps.web_api.backtest_candidates import read_backtest_candidate
from apps.web_api.candidate_quality import evaluate_candidate_quality
from apps.web_api.equivalence import annotate_metric_equivalence
from apps.web_api.jobs import BACKTEST_JOB_ACTION_IDS
from apps.web_api.jobs import JobRecord, collect_job_records, find_job_record
from apps.web_api.state_db import record_state_document
from apps.web_api.status import REPO_ROOT


MAX_SERIES_POINTS = 500
MAX_TRADES = 200
MAX_OBSERVATIONS = 100
MAX_PAPER_ORDERS = 200
MAX_HUMMINGBOT_EVENTS = 300


def build_job_result_view(
    job_id: str,
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object] | None:
    job = find_job_record(job_id, runtime_jobs, repo_root=repo_root)
    if job is None:
        return None

    action_id = str(job.get("action_id", ""))
    artifacts = _mapping(job.get("artifacts"))
    if action_id in BACKTEST_JOB_ACTION_IDS:
        data = _load_json_artifact(repo_root, artifacts, "backtest_json")
        if data is None:
            raise ValueError("backtest result artifact is not available")
        return _backtest_result_view(job, data, artifacts)
    if action_id == "run_paper_smoke":
        summary = _load_json_artifact(repo_root, artifacts, "summary_json")
        observations = _load_jsonl_artifact(repo_root, artifacts, "observation_jsonl")
        ledger_orders = _load_jsonl_artifact(repo_root, artifacts, "ledger_jsonl")
        if summary is None and not observations:
            raise ValueError("paper smoke result artifact is not available")
        return _paper_smoke_result_view(job, summary or {}, observations, ledger_orders, artifacts)
    if action_id == "collect_hummingbot_paper_events":
        report = _load_json_artifact(repo_root, artifacts, "collection_report_json")
        events = _load_jsonl_artifact(repo_root, artifacts, "events_jsonl")
        if report is None:
            raise ValueError("hummingbot event collection artifact is not available")
        return _hummingbot_events_result_view(job, report, events, artifacts)
    if action_id == "run_hummingbot_export_acceptance":
        acceptance = _load_json_artifact(repo_root, artifacts, "acceptance_json")
        events = _load_jsonl_input(repo_root, str(artifacts.get("events_jsonl", "")))
        if acceptance is None:
            raise ValueError("hummingbot acceptance artifact is not available")
        return _hummingbot_acceptance_result_view(job, acceptance, events, artifacts)
    raise ValueError("result view is only available for backtest, paper smoke and Hummingbot paper jobs")


def list_backtest_results(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    candidate = _candidate_with_quality(read_backtest_candidate(repo_root))
    candidate_job_id = str(candidate.get("job_id", "")) if candidate else ""
    results: list[dict[str, object]] = []
    for job in collect_job_records(runtime_jobs, repo_root=repo_root):
        if str(job.get("action_id", "")) not in BACKTEST_JOB_ACTION_IDS:
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        item = _backtest_result_item(job, repo_root)
        if item is None:
            continue
        item["selected_as_candidate"] = bool(candidate_job_id and item["job_id"] == candidate_job_id)
        results.append(item)
    results = annotate_metric_equivalence(results, id_key="job_id")
    if candidate is not None:
        for item in results:
            if str(item.get("job_id", "")) == candidate_job_id:
                candidate["equivalence"] = item.get("equivalence")
                break
    return {
        "results": results,
        "candidate": candidate,
        "candidate_path": str(BACKTEST_CANDIDATE_PATH),
    }


def confirm_backtest_candidate(
    job_id: str,
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
    operator_note: str = "",
) -> dict[str, object] | None:
    job = find_job_record(job_id, runtime_jobs, repo_root=repo_root)
    if job is None:
        return None
    if str(job.get("action_id", "")) not in BACKTEST_JOB_ACTION_IDS:
        raise ValueError("candidate can only be selected from backtest jobs")
    if str(job.get("status", "")) != "succeeded":
        raise ValueError("candidate can only be selected from succeeded backtest jobs")

    item = _backtest_result_item(job, repo_root)
    if item is None:
        raise ValueError("backtest result artifact is not available")

    payload = {
        "candidate_type": "backtest",
        "selected_at": datetime.now(tz=UTC).isoformat(),
        "operator_note": operator_note.strip()[:1000],
        "selected_as_candidate": True,
        **item,
    }
    candidate_path = repo_root / BACKTEST_CANDIDATE_PATH
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    record_state_document(
        key="backtest_candidate",
        source_path=str(BACKTEST_CANDIDATE_PATH),
        payload=payload,
        repo_root=repo_root,
    )
    return payload


def _backtest_result_item(job: Mapping[str, object], repo_root: Path) -> dict[str, object] | None:
    artifacts = _mapping(job.get("artifacts"))
    data = _load_json_artifact(repo_root, artifacts, "backtest_json")
    if data is None:
        return None
    metrics = _string_mapping(_mapping(data.get("metrics")))
    return {
        "job_id": str(job.get("job_id", "")),
        "status": str(job.get("status", "")),
        "created_at": str(job.get("created_at", "")),
        "completed_at": job.get("completed_at"),
        "strategy_id": str(data.get("strategy_id", "")),
        "artifact_path": str(artifacts.get("backtest_json", "")),
        "parameters": _string_mapping(_mapping(data.get("parameters"))),
        "metrics": metrics,
        "quality_gate": evaluate_candidate_quality(metrics),
    }


def _backtest_result_view(
    job: Mapping[str, object],
    data: Mapping[str, object],
    artifacts: Mapping[str, object],
) -> dict[str, object]:
    raw_series = _equity_series(data.get("equity_curve"))
    series = _sample(raw_series, MAX_SERIES_POINTS)
    raw_trades = _trade_rows(data.get("trades"))
    return {
        "job_id": str(job.get("job_id", "")),
        "kind": "backtest",
        "strategy_id": str(data.get("strategy_id", "")),
        "artifact_path": str(artifacts.get("backtest_json", "")),
        "parameters": _string_mapping(_mapping(data.get("parameters"))),
        "metrics": _metric_rows(_mapping(data.get("metrics"))),
        "series": series,
        "series_count": len(raw_series),
        "series_truncated": len(series) < len(raw_series),
        "trades": raw_trades[:MAX_TRADES],
        "trade_count": len(raw_trades),
        "trades_truncated": len(raw_trades) > MAX_TRADES,
        "monthly_returns": _monthly_return_rows(raw_series),
        "drawdown_episodes": _drawdown_episode_rows(raw_series),
        "trade_stats": _trade_stats(raw_trades),
    }


def _paper_smoke_result_view(
    job: Mapping[str, object],
    summary: Mapping[str, object],
    observations: list[dict[str, object]],
    ledger_orders: list[dict[str, object]],
    artifacts: Mapping[str, object],
) -> dict[str, object]:
    raw_series = _observation_equity_series(observations)
    series = _sample(raw_series, MAX_SERIES_POINTS)
    cycles = _paper_cycle_rows(observations)
    routed_orders = _paper_routed_order_rows(observations)
    ledger_rows = _paper_ledger_rows(ledger_orders)
    return {
        "job_id": str(job.get("job_id", "")),
        "kind": "paper_smoke",
        "artifact_path": str(artifacts.get("summary_json", "")),
        "parameters": _string_mapping(_mapping(job.get("parameters"))),
        "summary": _string_mapping(summary),
        "metrics": _paper_smoke_metric_rows(summary),
        "series": series,
        "series_count": len(raw_series),
        "series_truncated": len(series) < len(raw_series),
        "cycles": cycles[:MAX_OBSERVATIONS],
        "cycle_count": len(cycles),
        "cycles_truncated": len(cycles) > MAX_OBSERVATIONS,
        "orders": routed_orders[:MAX_PAPER_ORDERS],
        "order_count": len(routed_orders),
        "orders_truncated": len(routed_orders) > MAX_PAPER_ORDERS,
        "ledger_orders": ledger_rows[:MAX_PAPER_ORDERS],
        "ledger_order_count": len(ledger_rows),
        "ledger_orders_truncated": len(ledger_rows) > MAX_PAPER_ORDERS,
    }


def _hummingbot_events_result_view(
    job: Mapping[str, object],
    report: Mapping[str, object],
    events: list[dict[str, object]],
    artifacts: Mapping[str, object],
) -> dict[str, object]:
    summary = _mapping(report.get("summary"))
    event_rows = _hummingbot_event_rows(events)
    return {
        "job_id": str(job.get("job_id", "")),
        "kind": "hummingbot_events",
        "artifact_path": str(artifacts.get("collection_report_json", "")),
        "events_artifact_path": str(artifacts.get("events_jsonl", "")),
        "parameters": _string_mapping(_mapping(job.get("parameters"))),
        "metrics": _hummingbot_event_collection_metric_rows(report, summary),
        "event_types": _event_type_rows(summary.get("event_types"), event_rows),
        "events": event_rows[:MAX_HUMMINGBOT_EVENTS],
        "event_count": len(event_rows),
        "events_truncated": len(event_rows) > MAX_HUMMINGBOT_EVENTS,
    }


def _hummingbot_acceptance_result_view(
    job: Mapping[str, object],
    acceptance: Mapping[str, object],
    events: list[dict[str, object]],
    artifacts: Mapping[str, object],
) -> dict[str, object]:
    event_rows = _hummingbot_event_rows(events)
    return {
        "job_id": str(job.get("job_id", "")),
        "kind": "hummingbot_acceptance",
        "artifact_path": str(artifacts.get("acceptance_json", "")),
        "events_artifact_path": str(artifacts.get("events_jsonl", "")),
        "parameters": _string_mapping(_mapping(job.get("parameters"))),
        "metrics": _hummingbot_acceptance_metric_rows(acceptance),
        "event_types": _event_type_rows(None, event_rows),
        "events": event_rows[:MAX_HUMMINGBOT_EVENTS],
        "event_count": len(event_rows),
        "events_truncated": len(event_rows) > MAX_HUMMINGBOT_EVENTS,
    }


def _equity_series(value: object) -> list[dict[str, object]]:
    rows = value if isinstance(value, list) else []
    points: list[dict[str, object]] = []
    peak: Decimal | None = None
    for row in rows:
        item = _mapping(row)
        timestamp = str(item.get("timestamp", "")).strip()
        equity = _decimal(item.get("equity"))
        if not timestamp or equity is None:
            continue
        if peak is None or equity > peak:
            peak = equity
        drawdown = Decimal("0")
        if peak and peak != 0:
            drawdown = equity / peak - Decimal("1")
        points.append(
            {
                "timestamp": timestamp,
                "equity": float(equity),
                "drawdown": float(drawdown),
            }
        )
    return points


def _observation_equity_series(records: list[dict[str, object]]) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    peak: Decimal | None = None
    for record in records:
        if str(record.get("status", "")) != "ok":
            continue
        account = _mapping(record.get("account"))
        timestamp = str(record.get("completed_at") or record.get("started_at") or "").strip()
        equity = _decimal(account.get("equity"))
        if not timestamp or equity is None:
            continue
        if peak is None or equity > peak:
            peak = equity
        drawdown = Decimal("0")
        if peak and peak != 0:
            drawdown = equity / peak - Decimal("1")
        points.append(
            {
                "timestamp": timestamp,
                "equity": float(equity),
                "drawdown": float(drawdown),
            }
        )
    return points


def _trade_rows(value: object) -> list[dict[str, str]]:
    rows = value if isinstance(value, list) else []
    trades: list[dict[str, str]] = []
    for row in rows:
        item = _mapping(row)
        timestamp = str(item.get("timestamp", "")).strip()
        symbol = str(item.get("symbol", "")).strip()
        if not timestamp and not symbol:
            continue
        trades.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "side": str(item.get("side", "")).strip(),
                "price": _string(item.get("price")),
                "quantity": _string(item.get("quantity")),
                "notional": _string(item.get("notional")),
                "fee": _string(item.get("fee")),
                "target_weight": _string(item.get("target_weight")),
            }
        )
    return trades


def _monthly_return_rows(series: list[dict[str, object]]) -> list[dict[str, str]]:
    months: dict[str, dict[str, Decimal | str]] = {}
    for point in series:
        timestamp = str(point.get("timestamp", ""))
        month = timestamp[:7]
        if len(month) != 7:
            continue
        equity = _decimal(point.get("equity"))
        if equity is None:
            continue
        if month not in months:
            months[month] = {
                "month": month,
                "start_equity": equity,
                "end_equity": equity,
            }
        else:
            months[month]["end_equity"] = equity
    rows: list[dict[str, str]] = []
    for month in sorted(months):
        item = months[month]
        start = item["start_equity"]
        end = item["end_equity"]
        if not isinstance(start, Decimal) or not isinstance(end, Decimal):
            continue
        monthly_return = Decimal("0") if start == 0 else end / start - Decimal("1")
        rows.append(
            {
                "month": month,
                "start_equity": _format_decimal(start),
                "end_equity": _format_decimal(end),
                "return": _format_decimal(monthly_return),
            }
        )
    return rows[-36:]


def _drawdown_episode_rows(series: list[dict[str, object]]) -> list[dict[str, str]]:
    episodes: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for point in series:
        timestamp = str(point.get("timestamp", ""))
        drawdown = _decimal(point.get("drawdown")) or Decimal("0")
        if drawdown < 0 and current is None:
            current = {
                "start": timestamp,
                "trough": timestamp,
                "trough_drawdown": drawdown,
                "recovered_at": "",
                "status": "open",
            }
            continue
        if drawdown < 0 and current is not None:
            trough_drawdown = current.get("trough_drawdown")
            if isinstance(trough_drawdown, Decimal) and drawdown < trough_drawdown:
                current["trough"] = timestamp
                current["trough_drawdown"] = drawdown
            continue
        if drawdown >= 0 and current is not None:
            current["recovered_at"] = timestamp
            current["status"] = "recovered"
            episodes.append(current)
            current = None
    if current is not None:
        episodes.append(current)
    episodes.sort(key=lambda item: item.get("trough_drawdown", Decimal("0")))
    rows: list[dict[str, str]] = []
    for episode in episodes[:10]:
        trough_drawdown = episode.get("trough_drawdown")
        rows.append(
            {
                "start": str(episode.get("start", "")),
                "trough": str(episode.get("trough", "")),
                "recovered_at": str(episode.get("recovered_at", "")),
                "status": str(episode.get("status", "")),
                "trough_drawdown": _format_decimal(trough_drawdown if isinstance(trough_drawdown, Decimal) else Decimal("0")),
            }
        )
    return rows


def _trade_stats(trades: list[dict[str, str]]) -> dict[str, str]:
    buy_count = sum(1 for trade in trades if trade.get("side") == "buy")
    sell_count = sum(1 for trade in trades if trade.get("side") == "sell")
    symbols = {trade.get("symbol", "") for trade in trades if trade.get("symbol")}
    gross_notional = sum(
        ((_decimal(trade.get("notional")) or Decimal("0")) for trade in trades),
        Decimal("0"),
    )
    fees = sum(((_decimal(trade.get("fee")) or Decimal("0")) for trade in trades), Decimal("0"))
    average_notional = Decimal("0") if not trades else gross_notional / Decimal(len(trades))
    return {
        "trade_count": str(len(trades)),
        "buy_count": str(buy_count),
        "sell_count": str(sell_count),
        "symbol_count": str(len(symbols)),
        "gross_notional": _format_decimal(gross_notional),
        "average_notional": _format_decimal(average_notional),
        "fees": _format_decimal(fees),
    }


def _paper_cycle_rows(records: list[dict[str, object]]) -> list[dict[str, str]]:
    cycles: list[dict[str, str]] = []
    for record in records:
        account = _mapping(record.get("account"))
        cycles.append(
            {
                "cycle_number": _string(record.get("cycle_number")),
                "started_at": _string(record.get("started_at")),
                "completed_at": _string(record.get("completed_at")),
                "status": _string(record.get("status")),
                "equity": _string(account.get("equity")),
                "cash": _string(account.get("cash")),
                "gross_exposure": _string(account.get("gross_exposure")),
                "routed_order_count": _string(record.get("routed_order_count")),
                "approved_order_count": _string(record.get("approved_order_count")),
                "rejected_order_count": _string(record.get("rejected_order_count")),
                "market_data_complete": _string(record.get("market_data_complete")),
                "error": _string(record.get("error")),
            }
        )
    return cycles


def _paper_routed_order_rows(records: list[dict[str, object]]) -> list[dict[str, str]]:
    orders: list[dict[str, str]] = []
    for record in records:
        routed_orders = record.get("routed_orders")
        if not isinstance(routed_orders, list):
            continue
        for order in routed_orders:
            item = _mapping(order)
            if not item:
                continue
            orders.append(
                {
                    "cycle_number": _string(record.get("cycle_number")),
                    "completed_at": _string(record.get("completed_at")),
                    "intent_id": _string(item.get("intent_id")),
                    "risk_status": _string(item.get("risk_status")),
                    "risk_reason": _string(item.get("risk_reason")),
                    "external_order_id": _string(item.get("external_order_id")),
                }
            )
    return orders


def _paper_ledger_rows(rows: list[dict[str, object]]) -> list[dict[str, str]]:
    orders: list[dict[str, str]] = []
    for row in rows:
        item = _mapping(row)
        if not item:
            continue
        orders.append(
            {
                "created_at": _string(item.get("created_at")),
                "paper_order_id": _string(item.get("paper_order_id")),
                "intent_id": _string(item.get("intent_id")),
                "symbol": _string(item.get("symbol")),
                "side": _string(item.get("side")),
                "quantity": _string(item.get("quantity")),
                "fill_price": _string(item.get("fill_price")),
                "notional": _string(item.get("notional")),
                "fee": _string(item.get("fee")),
                "status": _string(item.get("status")),
            }
        )
    return orders


def _hummingbot_event_rows(events: list[dict[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for event in events:
        item = _mapping(event)
        rows.append(
            {
                "timestamp": _string(item.get("timestamp") or item.get("created_at")),
                "event_type": _string(item.get("event_type")),
                "client_order_id": _string(
                    item.get("client_order_id")
                    or item.get("order_id")
                    or item.get("order_id_str")
                ),
                "trading_pair": _string(item.get("trading_pair") or item.get("symbol")),
                "side": _string(item.get("side") or item.get("trade_type")),
                "status": _string(item.get("status") or item.get("order_status")),
                "price": _string(item.get("price")),
                "amount": _string(item.get("amount") or item.get("quantity")),
                "message": _string(item.get("message") or item.get("reason")),
            }
        )
    return rows


def _metric_rows(metrics: Mapping[str, object]) -> list[dict[str, str]]:
    keys = (
        "start_equity",
        "end_equity",
        "total_return",
        "max_drawdown",
        "tail_loss",
        "turnover",
        "trade_count",
        "total_fees",
        "traded_notional",
        "bars",
    )
    return [{"label": key, "value": _string(metrics.get(key))} for key in keys if metrics.get(key) is not None]


def _paper_smoke_metric_rows(summary: Mapping[str, object]) -> list[dict[str, str]]:
    keys = (
        "status",
        "cycles",
        "ok_cycles",
        "failed_cycles",
        "routed_orders",
        "approved_orders",
        "rejected_orders",
        "market_data_incomplete_cycles",
        "first_equity",
        "last_equity",
        "min_equity",
        "max_drawdown",
    )
    return [{"label": key, "value": _string(summary.get(key))} for key in keys if summary.get(key) is not None]


def _hummingbot_event_collection_metric_rows(
    report: Mapping[str, object],
    summary: Mapping[str, object],
) -> list[dict[str, str]]:
    values = {
        "decision": report.get("decision"),
        "session_id": report.get("session_id"),
        "event_count": summary.get("event_count"),
        "parse_errors": summary.get("parse_errors"),
        "truncated": summary.get("truncated"),
        "first_event": summary.get("first_event_type"),
        "last_event": summary.get("last_event_type"),
        "last_timestamp": summary.get("last_timestamp"),
    }
    return [{"label": key, "value": _string(value)} for key, value in values.items() if value is not None]


def _hummingbot_acceptance_metric_rows(acceptance: Mapping[str, object]) -> list[dict[str, str]]:
    reconciliation = _mapping(acceptance.get("reconciliation_summary"))
    session_gate = _mapping(acceptance.get("session_gate_summary"))
    package = _mapping(acceptance.get("package_summary"))
    alerts = acceptance.get("alerts")
    values = {
        "decision": acceptance.get("decision"),
        "session_id": acceptance.get("session_id"),
        "event_source": acceptance.get("event_source"),
        "events": reconciliation.get("event_count"),
        "submitted_orders": reconciliation.get("submitted_orders"),
        "terminal_orders": reconciliation.get("terminal_orders"),
        "session_gate": session_gate.get("decision"),
        "package": package.get("decision"),
        "alerts": len(alerts) if isinstance(alerts, list) else 0,
    }
    return [{"label": key, "value": _string(value)} for key, value in values.items() if value is not None]


def _event_type_rows(value: object, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if isinstance(value, dict) and value:
        counts = {str(key): _string(item) for key, item in value.items()}
    else:
        counts: dict[str, str] = {}
        for row in rows:
            event_type = row.get("event_type", "") or "unknown"
            counts[event_type] = str(int(counts.get(event_type, "0") or "0") + 1)
    return [
        {"event_type": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: (-_intish(item[1]), item[0]))
    ]


def _sample(points: list[dict[str, object]], max_points: int) -> list[dict[str, object]]:
    if len(points) <= max_points:
        return points
    if max_points <= 1:
        return points[:1]
    step = (len(points) - 1) / (max_points - 1)
    return [points[round(index * step)] for index in range(max_points)]


def _load_json_artifact(repo_root: Path, artifacts: Mapping[str, object], key: str) -> dict[str, object] | None:
    value = artifacts.get(key)
    if not isinstance(value, str):
        return None
    path = _safe_artifact_path(repo_root, value)
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _load_jsonl_artifact(repo_root: Path, artifacts: Mapping[str, object], key: str) -> list[dict[str, object]]:
    value = artifacts.get(key)
    if not isinstance(value, str):
        return []
    path = _safe_artifact_path(repo_root, value)
    if path is None or not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if isinstance(payload, dict):
                    rows.append(payload)
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def _load_jsonl_input(repo_root: Path, value: str) -> list[dict[str, object]]:
    if not value:
        return []
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if isinstance(payload, dict):
                    rows.append(payload)
    except (OSError, json.JSONDecodeError):
        return []
    return rows


def _safe_artifact_path(repo_root: Path, relative_path: str) -> Path | None:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    absolute = (repo_root / path).resolve()
    try:
        absolute.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return absolute


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _string_mapping(value: Mapping[str, object]) -> dict[str, str]:
    return {str(key): _string(item) for key, item in value.items()}


def _string(value: object) -> str:
    return "" if value is None else str(value)


def _intish(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _candidate_with_quality(candidate: dict[str, object] | None) -> dict[str, object] | None:
    if candidate is None:
        return None
    payload = dict(candidate)
    if "quality_gate" not in payload:
        metrics = _string_mapping(_mapping(payload.get("metrics")))
        if metrics:
            payload["quality_gate"] = evaluate_candidate_quality(metrics)
    return payload


def _decimal(value: object) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
