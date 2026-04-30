"""Read-only live readiness summary for the web dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from apps.web_api.status import CLOSURE_REPORT_PATH
from apps.web_api.status import COOLDOWN_REPORT_PATH
from apps.web_api.status import POST_TRADE_REPORT_PATH
from apps.web_api.status import REPO_ROOT
from apps.web_api.state_db import record_state_document


LIVE_READINESS_DISPOSITION_PATH = Path("reports/web_reviews/live_readiness_disposition.json")

LIVE_DISPOSITION_OPTIONS = {
    "keep_live_blocked": {
        "label": "保持 Live 阻断",
        "description": "记录当前 Web 继续阻断 live runner 和 live order submission。",
        "target_step_id": "live_readiness",
        "severity": "warning",
    },
    "request_cooldown_review": {
        "label": "等待或重跑 Cooldown Review",
        "description": "记录当前阻断主要来自 cooldown，需要等待窗口或线下重跑 cooldown review。",
        "target_step_id": "cooldown_review",
        "severity": "warning",
    },
    "request_connector_review": {
        "label": "复核 Live Connector Preflight",
        "description": "记录需要线下复核 connector preflight、凭据权限和字段脱敏结果。",
        "target_step_id": "live_readiness",
        "severity": "warning",
    },
    "operator_review_only": {
        "label": "进入人工复核",
        "description": "记录仅进入人工 review，不改变 Web live 阻断状态。",
        "target_step_id": "first_live_batch",
        "severity": "neutral",
    },
}

LIVE_REPORTS = (
    (
        "live_readiness",
        "Live readiness",
        Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_1_live_readiness.json"),
    ),
    (
        "activation_checklist",
        "Activation checklist",
        Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.json"),
    ),
    (
        "connector_preflight",
        "Connector preflight",
        Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.json"),
    ),
    (
        "first_batch_plan",
        "First live batch plan",
        Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan_low_funds_50.json"),
    ),
    ("post_trade", "Post-trade reconciliation", POST_TRADE_REPORT_PATH),
    ("cooldown", "Cooldown review", COOLDOWN_REPORT_PATH),
    ("initial_closure", "Initial closure", CLOSURE_REPORT_PATH),
)


def build_live_readiness_summary(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    reports = [_report_item(repo_root, report_id, label, path) for report_id, label, path in LIVE_REPORTS]
    available_reports = [report for report in reports if report["exists"]]
    blockers = _blockers(available_reports)
    next_live = _next_live_decision(repo_root)
    return {
        "status": "blocked" if blockers else "review_only",
        "live_actions_exposed": False,
        "live_order_submission_exposed": False,
        "live_runner_exposed": False,
        "next_live_decision": next_live.get("decision", "unknown"),
        "next_live_reason": next_live.get("reason", ""),
        "next_review_not_before": next_live.get("next_review_not_before", ""),
        "reports": reports,
        "blockers": blockers,
        "recommended_actions": _recommended_actions(blockers, next_live),
        "disposition_options": _disposition_options(blockers),
        "recorded_disposition": read_live_readiness_disposition(repo_root),
    }


def record_live_readiness_disposition(
    *,
    decision_id: str,
    repo_root: Path = REPO_ROOT,
    operator_note: str = "",
) -> dict[str, object]:
    if decision_id not in LIVE_DISPOSITION_OPTIONS:
        raise ValueError(f"unsupported live readiness disposition: {decision_id}")
    summary = build_live_readiness_summary(repo_root)
    option = LIVE_DISPOSITION_OPTIONS[decision_id]
    payload = {
        "decision_id": decision_id,
        "label": option["label"],
        "recorded_at": _now_iso(),
        "operator_note": operator_note.strip()[:1000],
        "live_summary_status": summary["status"],
        "next_live_decision": summary["next_live_decision"],
        "blockers": summary["blockers"],
        "next_step_id": option["target_step_id"],
        "live_runner_exposed": False,
        "live_order_submission_exposed": False,
    }
    output = repo_root / LIVE_READINESS_DISPOSITION_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    record_state_document(
        key="live_readiness_disposition",
        source_path=str(LIVE_READINESS_DISPOSITION_PATH),
        payload=payload,
        repo_root=repo_root,
    )
    return payload


def read_live_readiness_disposition(repo_root: Path = REPO_ROOT) -> dict[str, object] | None:
    path = repo_root / LIVE_READINESS_DISPOSITION_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _report_item(repo_root: Path, report_id: str, label: str, path: Path) -> dict[str, object]:
    payload = _read_json(repo_root / path)
    alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
    warning_alerts = [alert for alert in alerts if str(_mapping(alert).get("severity", "")).upper() == "WARN"]
    critical_alerts = [alert for alert in alerts if str(_mapping(alert).get("severity", "")).upper() == "CRITICAL"]
    decision = str(payload.get("decision") or payload.get("status") or "missing")
    return {
        "report_id": report_id,
        "label": label,
        "path": str(path),
        "exists": bool(payload),
        "decision": decision,
        "generated_at": str(payload.get("generated_at", "")),
        "alerts": len(alerts),
        "critical_alerts": len(critical_alerts),
        "warning_alerts": len(warning_alerts),
    }


def _blockers(reports: list[dict[str, object]]) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    for report in reports:
        decision = str(report.get("decision", ""))
        critical_count = int(str(report.get("critical_alerts", 0)))
        if "blocked" in decision or critical_count > 0:
            blockers.append(
                {
                    "report_id": report["report_id"],
                    "title": str(report["label"]),
                    "message": f"decision={decision}, critical_alerts={critical_count}",
                    "severity": "CRITICAL",
                }
            )
    next_live = next((report for report in reports if report.get("report_id") == "cooldown"), None)
    if next_live and "active" in str(next_live.get("decision", "")):
        blockers.append(
            {
                "report_id": "cooldown",
                "title": "Cooldown active",
                "message": "Cooldown review is still active; live actions must remain blocked.",
                "severity": "WARN",
            }
        )
    return blockers


def _next_live_decision(repo_root: Path) -> dict[str, object]:
    closure = _read_json(repo_root / CLOSURE_REPORT_PATH)
    next_live = closure.get("next_live_decision")
    return dict(next_live) if isinstance(next_live, dict) else {}


def _recommended_actions(blockers: list[dict[str, object]], next_live: Mapping[str, object]) -> list[str]:
    actions = [
        "Keep Web live runner and live order submission disabled.",
        "Use this panel for review only; do not treat it as operator signoff.",
    ]
    if blockers:
        actions.append("Resolve blocker reports and rerun the corresponding offline review before any live discussion.")
    if str(next_live.get("next_review_not_before", "")):
        actions.append(f"Do not review another live batch before {next_live['next_review_not_before']}.")
    return actions


def _disposition_options(blockers: list[dict[str, object]]) -> list[dict[str, object]]:
    blocker_ids = {str(blocker.get("report_id", "")) for blocker in blockers}
    return [
        {"decision_id": "keep_live_blocked", **LIVE_DISPOSITION_OPTIONS["keep_live_blocked"], "enabled": True},
        {
            "decision_id": "request_cooldown_review",
            **LIVE_DISPOSITION_OPTIONS["request_cooldown_review"],
            "enabled": "cooldown" in blocker_ids,
        },
        {
            "decision_id": "request_connector_review",
            **LIVE_DISPOSITION_OPTIONS["request_connector_review"],
            "enabled": "connector_preflight" in blocker_ids or "live_readiness" in blocker_ids,
        },
        {"decision_id": "operator_review_only", **LIVE_DISPOSITION_OPTIONS["operator_review_only"], "enabled": True},
    ]


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(tz=UTC).isoformat()
