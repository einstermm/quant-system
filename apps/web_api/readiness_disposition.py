"""Disposition workflow for blocked paper readiness reports."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Mapping

from apps.web_api.jobs import JobRecord, collect_job_records
from apps.web_api.backtest_candidates import read_backtest_candidate
from apps.web_api.readiness_disposition_state import READINESS_DISPOSITION_PATH
from apps.web_api.readiness_disposition_state import disposition_resolution
from apps.web_api.readiness_disposition_state import enriched_recorded_disposition
from apps.web_api.readiness_disposition_state import read_recorded_disposition
from apps.web_api.state_db import record_state_document
from apps.web_api.status import REPO_ROOT


DISPOSITION_OPTIONS = {
    "return_to_research": {
        "label": "回到研究阶段更换候选",
        "description": "记录当前候选未通过准入，并返回研究阶段选择其他回测或重新跑参数。",
        "target_step_id": "research_backtest",
        "severity": "warning",
    },
    "request_capacity_evidence": {
        "label": "补齐容量压力证据",
        "description": "记录需要为当前候选补齐 capacity stress evidence，再重新生成 Paper 准入。",
        "target_step_id": "research_backtest",
        "severity": "warning",
    },
    "rerun_readiness_after_fix": {
        "label": "修复后重新生成准入",
        "description": "用于记录证据或候选已修复，下一步应重新运行 Paper 准入任务。",
        "target_step_id": "paper_readiness",
        "severity": "neutral",
    },
}


def build_readiness_disposition(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    latest = _latest_readiness_report(runtime_jobs, repo_root)
    current_candidate = read_backtest_candidate(repo_root)
    recorded = enriched_recorded_disposition(read_recorded_disposition(repo_root), current_candidate)
    resolution = disposition_resolution(recorded, current_candidate)
    if latest is None:
        return {
            "status": "not_available",
            "latest_job": None,
            "readiness_artifact": "",
            "candidate": None,
            "alerts": [],
            "critical_alerts": 0,
            "warning_alerts": 0,
            "recommended_actions": [],
            "repair_guidance": [],
            "disposition_options": [],
            "recorded_disposition": recorded,
            "disposition_resolution": resolution,
        }

    job, artifact_path, report = latest
    alerts = [_alert_payload(alert) for alert in _list(report.get("alerts"))]
    critical_alerts = sum(1 for alert in alerts if alert["severity"] == "CRITICAL")
    warning_alerts = sum(1 for alert in alerts if alert["severity"] == "WARN")
    status = str(report.get("status", "unknown"))
    return {
        "status": status,
        "latest_job": _compact_job(job),
        "readiness_artifact": artifact_path,
        "candidate": report.get("candidate_backtest") if isinstance(report.get("candidate_backtest"), dict) else None,
        "alerts": alerts,
        "critical_alerts": critical_alerts,
        "warning_alerts": warning_alerts,
        "recommended_actions": [str(action) for action in _list(report.get("recommended_actions"))],
        "repair_guidance": _repair_guidance(status, alerts, report),
        "disposition_options": _disposition_options(status, alerts, resolution),
        "recorded_disposition": recorded,
        "disposition_resolution": resolution,
    }


def record_readiness_disposition(
    *,
    decision_id: str,
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
    operator_note: str = "",
) -> dict[str, object]:
    if decision_id not in DISPOSITION_OPTIONS:
        raise ValueError(f"unsupported readiness disposition: {decision_id}")
    disposition = build_readiness_disposition(runtime_jobs, repo_root=repo_root)
    if disposition["status"] == "not_available":
        raise ValueError("paper readiness report is not available")

    option = DISPOSITION_OPTIONS[decision_id]
    candidate = _mapping(disposition.get("candidate"))
    latest_job = _mapping(disposition.get("latest_job"))
    payload = {
        "decision_id": decision_id,
        "label": option["label"],
        "recorded_at": datetime.now(tz=UTC).isoformat(),
        "operator_note": operator_note.strip()[:1000],
        "readiness_status": disposition["status"],
        "readiness_artifact": disposition["readiness_artifact"],
        "latest_readiness_job_id": latest_job.get("job_id", ""),
        "candidate_job_id": candidate.get("job_id", ""),
        "candidate_strategy_id": candidate.get("strategy_id", ""),
        "blocking_alerts": [
            alert
            for alert in _list(disposition.get("alerts"))
            if _mapping(alert).get("severity") == "CRITICAL"
        ],
        "next_step_id": option["target_step_id"],
    }
    output = repo_root / READINESS_DISPOSITION_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    record_state_document(
        key="paper_readiness_disposition",
        source_path=str(READINESS_DISPOSITION_PATH),
        payload=payload,
        repo_root=repo_root,
    )
    return payload


def _latest_readiness_report(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path,
) -> tuple[Mapping[str, object], str, dict[str, object]] | None:
    for job in collect_job_records(runtime_jobs, repo_root=repo_root):
        if str(job.get("action_id", "")) != "generate_paper_readiness":
            continue
        artifacts = _mapping(job.get("artifacts"))
        readiness_path = artifacts.get("readiness_json")
        if not isinstance(readiness_path, str):
            continue
        absolute = _safe_artifact_path(repo_root, readiness_path)
        if absolute is None or not absolute.exists():
            continue
        try:
            payload = json.loads(absolute.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return job, readiness_path, payload
    return None


def _disposition_options(
    status: str,
    alerts: list[dict[str, object]],
    resolution: Mapping[str, object],
) -> list[dict[str, object]]:
    if status in {"paper_ready", "paper_ready_with_warnings"}:
        return [
            {
                "decision_id": "rerun_readiness_after_fix",
                **DISPOSITION_OPTIONS["rerun_readiness_after_fix"],
                "enabled": resolution.get("resolution_status") != "requires_new_candidate",
            }
        ]
    if status != "blocked":
        return []

    alert_titles = {str(alert.get("title", "")) for alert in alerts}
    needs_capacity = "Capacity below minimum" in alert_titles
    return [
        {
            "decision_id": "return_to_research",
            **DISPOSITION_OPTIONS["return_to_research"],
            "enabled": True,
        },
        {
            "decision_id": "request_capacity_evidence",
            **DISPOSITION_OPTIONS["request_capacity_evidence"],
            "enabled": needs_capacity,
        },
        {
            "decision_id": "rerun_readiness_after_fix",
            **DISPOSITION_OPTIONS["rerun_readiness_after_fix"],
            "enabled": resolution.get("resolution_status") == "superseded",
        },
    ]


def _repair_guidance(
    status: str,
    alerts: list[dict[str, object]],
    report: Mapping[str, object],
) -> list[dict[str, object]]:
    if status != "blocked":
        return []
    candidate = _mapping(report.get("candidate_backtest"))
    has_candidate = bool(str(candidate.get("job_id", "")).strip())
    titles = {str(alert.get("title", "")) for alert in alerts}
    guidance: list[dict[str, object]] = []
    if _has_walk_forward_alert(titles):
        guidance.extend(
            [
                {
                    "guidance_id": "rescan_parameters",
                    "label": "重新扫描参数",
                    "description": "Walk-forward 稳定性不足，先回到研究阶段扩大或调整参数扫描范围。",
                    "target_step_id": "research_backtest",
                    "action_id": "run_parameter_scan",
                    "severity": "warning",
                    "enabled": True,
                },
                {
                    "guidance_id": "rerun_candidate_walk_forward",
                    "label": "重跑候选 Walk-forward",
                    "description": "候选参数或证据修复后，重新生成当前候选的专属 walk-forward 证据。",
                    "target_step_id": "research_backtest",
                    "action_id": "run_candidate_walk_forward",
                    "severity": "warning",
                    "enabled": has_candidate,
                },
            ]
        )
    if _has_capacity_alert(titles):
        guidance.append(
            {
                "guidance_id": "rerun_candidate_capacity",
                "label": "重跑候选 Capacity Stress",
                "description": "容量证据不足或容量低于门槛，重新生成当前候选的专属 capacity stress 证据。",
                "target_step_id": "research_backtest",
                "action_id": "run_candidate_capacity_stress",
                "severity": "warning",
                "enabled": has_candidate,
            }
        )
    if guidance:
        guidance.append(
            {
                "guidance_id": "rerun_paper_readiness",
                "label": "修复后重新生成准入",
                "description": "候选证据修复完成后，回到 Paper 准入门禁重新生成准入报告。",
                "target_step_id": "paper_readiness",
                "action_id": "generate_paper_readiness",
                "severity": "neutral",
                "enabled": has_candidate,
            }
        )
    return guidance


def _has_walk_forward_alert(titles: set[str]) -> bool:
    return bool(
        titles
        & {
            "Positive fold ratio too low",
            "Median return below threshold",
            "Worst test loss too large",
            "Return concentration",
            "Candidate strategy mismatch",
        }
    )


def _has_capacity_alert(titles: set[str]) -> bool:
    return any("Capacity" in title or "Participation" in title for title in titles)


def _alert_payload(alert: object) -> dict[str, object]:
    payload = _mapping(alert)
    title = str(payload.get("title", ""))
    return {
        "severity": str(payload.get("severity", "")),
        "title": title,
        "message": str(payload.get("message", "")),
        "created_at": str(payload.get("created_at", "")),
        "hint": _alert_hint(title),
    }


def _alert_hint(title: str) -> str:
    if title in {
        "Positive fold ratio too low",
        "Median return below threshold",
        "Worst test loss too large",
        "Return concentration",
    }:
        return "回到研究阶段更换候选、调整策略参数，或重新生成 walk-forward 证据。"
    if title == "Capacity below minimum":
        return "补齐当前候选的容量压力证据；如果容量仍不足，降低资金目标或更换候选。"
    if title == "Candidate strategy mismatch":
        return "重新选择匹配策略的候选，或补齐该策略对应的 walk-forward/capacity evidence。"
    if "drawdown" in title.lower() or "tail" in title.lower():
        return "检查风险参数、回撤控制和尾部亏损阈值，再重新跑候选验证。"
    return "查看 readiness 报告和候选详情后决定是否回到研究阶段。"


def _compact_job(job: Mapping[str, object]) -> dict[str, object]:
    return {
        "job_id": str(job.get("job_id", "")),
        "status": str(job.get("status", "")),
        "created_at": str(job.get("created_at", "")),
        "completed_at": job.get("completed_at"),
        "artifacts": _mapping(job.get("artifacts")),
        "parameters": _mapping(job.get("parameters")),
    }


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


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []
