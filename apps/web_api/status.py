"""Read-only status aggregation for the web API."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

FEATURE_INVENTORY_PATH = Path("docs/v0_feature_inventory.md")
CLOSURE_REPORT_PATH = Path(
    "reports/live_readiness/"
    "crypto_relative_strength_v1_phase_6_9_initial_closure_position_plan_low_funds_50/"
    "initial_closure_report.json"
)
COOLDOWN_REPORT_PATH = Path(
    "reports/live_readiness/"
    "crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/"
    "cooldown_review.json"
)
POST_TRADE_REPORT_PATH = Path(
    "reports/live_readiness/"
    "crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/"
    "post_trade_report.json"
)


def build_system_status(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    """Build the first dashboard payload from committed reports and docs."""

    feature_inventory = _read_text(repo_root / FEATURE_INVENTORY_PATH)
    closure = _read_json(repo_root / CLOSURE_REPORT_PATH)
    cooldown = _read_json(repo_root / COOLDOWN_REPORT_PATH)
    post_trade = _read_json(repo_root / POST_TRADE_REPORT_PATH)

    next_live = _dict(closure.get("next_live_decision"))
    position = _dict(closure.get("position_lifecycle_plan"))
    closure_summary = _dict(closure.get("closure_summary"))
    cooldown_window = _dict(cooldown.get("cooldown_window"))
    fill_summary = _dict(post_trade.get("fill_summary"))
    order_checks = _dict(post_trade.get("order_checks"))

    return {
        "service": "quant-system-web-api",
        "repository": str(repo_root),
        "feature_inventory": {
            "path": str(FEATURE_INVENTORY_PATH),
            "current_version": _extract_current_version(feature_inventory),
        },
        "safety": {
            "web_mode": "read_only",
            "live_order_submission_exposed": False,
            "live_runner_exposed": False,
        },
        "live": {
            "status": str(closure.get("status", "unknown")),
            "strategy_id": str(closure.get("strategy_id", "")),
            "account_id": str(closure.get("account_id", "")),
            "generated_at": str(closure.get("generated_at", "")),
            "initial_flow_closed": bool(closure_summary.get("initial_flow_closed", False)),
            "evidence_complete": bool(closure_summary.get("evidence_complete", False)),
            "next_decision": str(next_live.get("decision", "unknown")),
            "next_decision_reason": str(next_live.get("reason", "")),
            "cooldown_elapsed": bool(next_live.get("cooldown_elapsed", False)),
            "next_review_not_before": str(next_live.get("next_review_not_before", "")),
            "allowed_pairs": list(next_live.get("allowed_pairs", []))
            if isinstance(next_live.get("allowed_pairs"), list)
            else [],
            "max_batch_notional": str(next_live.get("max_batch_notional", "")),
            "max_order_notional": str(next_live.get("max_order_notional", "")),
            "alerts": _alerts(closure),
        },
        "cooldown": {
            "status": str(cooldown.get("status", "unknown")),
            "completed_at": str(cooldown_window.get("completed_at", "")),
            "minimum_cooldown_hours": str(cooldown_window.get("minimum_cooldown_hours", "")),
            "elapsed_hours": str(cooldown_window.get("elapsed_hours", "")),
            "next_review_not_before": str(cooldown_window.get("next_review_not_before", "")),
            "cooldown_elapsed": bool(cooldown_window.get("cooldown_elapsed", False)),
        },
        "position": {
            "stance": str(position.get("stance", "unknown")),
            "trading_pair": str(position.get("trading_pair", "")),
            "strategy_net_base_quantity": str(position.get("strategy_net_base_quantity", "")),
            "entry_cost_basis_quote": str(position.get("entry_cost_basis_quote", "")),
            "exit_requires_activation": bool(position.get("exit_requires_activation", True)),
        },
        "post_trade": {
            "status": str(post_trade.get("status", "unknown")),
            "expected_orders": int(order_checks.get("expected_orders", 0) or 0),
            "submitted_orders": int(order_checks.get("submitted_orders", 0) or 0),
            "filled_orders": int(order_checks.get("filled_orders", 0) or 0),
            "db_fills": int(order_checks.get("db_fills", 0) or 0),
            "gross_quote_notional": str(fill_summary.get("gross_quote_notional", "")),
            "net_base_quantity": str(fill_summary.get("net_base_quantity", "")),
            "average_price_quote": str(fill_summary.get("average_price_quote", "")),
        },
        "artifacts": {
            "feature_inventory": str(FEATURE_INVENTORY_PATH),
            "closure_report": str(CLOSURE_REPORT_PATH),
            "cooldown_report": str(COOLDOWN_REPORT_PATH),
            "post_trade_report": str(POST_TRADE_REPORT_PATH),
        },
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _extract_current_version(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("当前版本定位："):
            raw = line.split("：", 1)[1].strip()
            match = re.search(r"`([^`]+)`", raw)
            if match:
                return match.group(1)
            return raw.rstrip("。").strip("`")
    return "unknown"


def _alerts(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_alerts = payload.get("alerts", [])
    if not isinstance(raw_alerts, list):
        return []
    alerts: list[dict[str, str]] = []
    for item in raw_alerts:
        if not isinstance(item, dict):
            continue
        alerts.append(
            {
                "severity": str(item.get("severity", "")),
                "title": str(item.get("title", "")),
                "message": str(item.get("message", "")),
                "created_at": str(item.get("created_at", "")),
            }
        )
    return alerts


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
