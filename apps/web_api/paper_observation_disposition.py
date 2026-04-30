"""Disposition workflow for local paper observation anomalies."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Mapping

from apps.web_api.jobs import JobRecord, collect_job_records
from apps.web_api.state_db import record_state_document
from apps.web_api.status import REPO_ROOT


PAPER_OBSERVATION_DISPOSITION_PATH = Path("reports/web_reviews/paper_observation_disposition.json")

PAPER_OBSERVATION_DISPOSITION_OPTIONS = {
    "rerun_paper_smoke": {
        "label": "按当前参数重跑 Paper Smoke",
        "description": "用于处理偶发运行失败或临时数据问题，回到本地 Paper 观察阶段重新运行。",
        "target_step_id": "local_paper_observation",
        "severity": "neutral",
    },
    "rerun_with_market_refresh": {
        "label": "刷新行情后重跑",
        "description": "当行情缺失、不完整或过旧时，开启行情刷新参数后重新运行 Paper Smoke。",
        "target_step_id": "local_paper_observation",
        "severity": "warning",
    },
    "review_risk_limits": {
        "label": "回到准入复核风控限制",
        "description": "当 Paper 订单被风控拒绝时，回到 Paper 准入阶段复核风险限制和容量证据。",
        "target_step_id": "paper_readiness",
        "severity": "warning",
    },
    "hold_live_promotion": {
        "label": "暂停进入 Live",
        "description": "记录当前 Paper 观察存在异常，暂停后续 live 推进，等待人工复核。",
        "target_step_id": "local_paper_observation",
        "severity": "warning",
    },
}


def build_paper_observation_disposition(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    latest = _latest_paper_smoke(runtime_jobs, repo_root)
    recorded = _read_recorded_disposition(repo_root)
    if latest is None:
        return {
            "status": "not_available",
            "latest_job": None,
            "summary_artifact": "",
            "observation_artifact": "",
            "ledger_artifact": "",
            "summary": {},
            "alerts": [],
            "recommended_actions": [],
            "disposition_options": [],
            "recorded_disposition": recorded,
        }

    job, summary_artifact, observation_artifact, ledger_artifact, summary, observations = latest
    alerts = _observation_alerts(job, summary, observations)
    summary_status = str(summary.get("status", "")).strip() or str(job.get("status", "unknown"))
    status = "ok" if not alerts and summary_status == "ok" else "attention_required"
    if str(job.get("status", "")) != "succeeded":
        status = "job_not_succeeded"
    return {
        "status": status,
        "latest_job": _compact_job(job),
        "summary_artifact": summary_artifact,
        "observation_artifact": observation_artifact,
        "ledger_artifact": ledger_artifact,
        "summary": _string_mapping(summary),
        "alerts": alerts,
        "recommended_actions": _recommended_actions(alerts),
        "disposition_options": _disposition_options(alerts),
        "recorded_disposition": recorded,
    }


def record_paper_observation_disposition(
    *,
    decision_id: str,
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
    operator_note: str = "",
) -> dict[str, object]:
    if decision_id not in PAPER_OBSERVATION_DISPOSITION_OPTIONS:
        raise ValueError(f"unsupported paper observation disposition: {decision_id}")
    disposition = build_paper_observation_disposition(runtime_jobs, repo_root=repo_root)
    if disposition["status"] == "not_available":
        raise ValueError("paper observation report is not available")

    option = PAPER_OBSERVATION_DISPOSITION_OPTIONS[decision_id]
    latest_job = _mapping(disposition.get("latest_job"))
    payload = {
        "decision_id": decision_id,
        "label": option["label"],
        "recorded_at": datetime.now(tz=UTC).isoformat(),
        "operator_note": operator_note.strip()[:1000],
        "observation_status": disposition["status"],
        "latest_observation_job_id": latest_job.get("job_id", ""),
        "summary_artifact": disposition.get("summary_artifact", ""),
        "blocking_alerts": _list(disposition.get("alerts")),
        "next_step_id": option["target_step_id"],
    }
    output = repo_root / PAPER_OBSERVATION_DISPOSITION_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    record_state_document(
        key="paper_observation_disposition",
        source_path=str(PAPER_OBSERVATION_DISPOSITION_PATH),
        payload=payload,
        repo_root=repo_root,
    )
    return payload


def _latest_paper_smoke(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path,
) -> tuple[Mapping[str, object], str, str, str, dict[str, object], list[dict[str, object]]] | None:
    for job in collect_job_records(runtime_jobs, repo_root=repo_root):
        if str(job.get("action_id", "")) != "run_paper_smoke":
            continue
        artifacts = _mapping(job.get("artifacts"))
        summary_artifact = str(artifacts.get("summary_json", ""))
        observation_artifact = str(artifacts.get("observation_jsonl", ""))
        ledger_artifact = str(artifacts.get("ledger_jsonl", ""))
        summary = _load_json_artifact(repo_root, summary_artifact)
        observations = _load_jsonl_artifact(repo_root, observation_artifact)
        return job, summary_artifact, observation_artifact, ledger_artifact, summary or {}, observations
    return None


def _observation_alerts(
    job: Mapping[str, object],
    summary: Mapping[str, object],
    observations: list[dict[str, object]],
) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []
    job_status = str(job.get("status", ""))
    if job_status != "succeeded":
        alerts.append(
            _alert(
                "CRITICAL",
                "Paper job did not succeed",
                f"最新 Paper Smoke 任务状态为 {job_status or 'unknown'}。",
                "查看任务 stderr/error，修复后重新运行 Paper Smoke。",
            )
        )

    failed_cycles = _int(summary.get("failed_cycles"))
    if failed_cycles > 0:
        errors = [
            str(record.get("error", "")).strip()
            for record in observations
            if str(record.get("status", "")) == "failed" and str(record.get("error", "")).strip()
        ]
        message = f"{failed_cycles} 个 observation cycle 失败。"
        if errors:
            message = f"{message} 最近错误：{errors[-1]}"
        alerts.append(
            _alert(
                "CRITICAL",
                "Failed observation cycles",
                message,
                "先处理 cycle 错误，再重跑 Paper Smoke 验证。",
            )
        )

    rejected_orders = _int(summary.get("rejected_orders"))
    if rejected_orders > 0:
        reasons = sorted(
            {
                str(order.get("risk_reason", "")).strip()
                for record in observations
                for order in _list(record.get("routed_orders"))
                if _mapping(order).get("risk_status") != "approved"
                and str(_mapping(order).get("risk_reason", "")).strip()
            }
        )
        detail = f"{rejected_orders} 个 Paper 订单被风控拒绝。"
        if reasons:
            detail = f"{detail} 原因：{'; '.join(reasons[:3])}"
        alerts.append(
            _alert(
                "WARN",
                "Rejected paper orders",
                detail,
                "复核风险限制、容量压力证据和候选参数后再继续推进。",
            )
        )

    incomplete_cycles = _int(summary.get("market_data_incomplete_cycles"))
    if incomplete_cycles > 0:
        alerts.append(
            _alert(
                "WARN",
                "Market data incomplete",
                f"{incomplete_cycles} 个 cycle 的行情数据不完整或质量未通过。",
                "开启运行前刷新行情，或先补齐本地 SQLite K 线后重跑。",
            )
        )

    if not summary and job_status == "succeeded":
        alerts.append(
            _alert(
                "WARN",
                "Paper summary missing",
                "任务成功但没有找到 observation summary 产物。",
                "查看任务产物路径，必要时重新运行 Paper Smoke。",
            )
        )
    return alerts


def _recommended_actions(alerts: list[dict[str, object]]) -> list[str]:
    titles = {str(alert.get("title", "")) for alert in alerts}
    actions: list[str] = []
    if "Market data incomplete" in titles:
        actions.append("开启行情刷新参数后重新运行 Paper Smoke")
    if "Rejected paper orders" in titles:
        actions.append("回到 Paper 准入阶段复核风控限制")
    if "Paper job did not succeed" in titles or "Failed observation cycles" in titles or "Paper summary missing" in titles:
        actions.append("修复错误后重跑 Paper Smoke")
    if alerts:
        actions.append("异常未关闭前暂停进入 Live")
    return actions


def _disposition_options(alerts: list[dict[str, object]]) -> list[dict[str, object]]:
    titles = {str(alert.get("title", "")) for alert in alerts}
    if not alerts:
        return []
    return [
        {
            "decision_id": "rerun_paper_smoke",
            **PAPER_OBSERVATION_DISPOSITION_OPTIONS["rerun_paper_smoke"],
            "enabled": True,
        },
        {
            "decision_id": "rerun_with_market_refresh",
            **PAPER_OBSERVATION_DISPOSITION_OPTIONS["rerun_with_market_refresh"],
            "enabled": "Market data incomplete" in titles or "Paper summary missing" in titles,
        },
        {
            "decision_id": "review_risk_limits",
            **PAPER_OBSERVATION_DISPOSITION_OPTIONS["review_risk_limits"],
            "enabled": "Rejected paper orders" in titles,
        },
        {
            "decision_id": "hold_live_promotion",
            **PAPER_OBSERVATION_DISPOSITION_OPTIONS["hold_live_promotion"],
            "enabled": True,
        },
    ]


def _compact_job(job: Mapping[str, object]) -> dict[str, object]:
    return {
        "job_id": str(job.get("job_id", "")),
        "action_id": str(job.get("action_id", "")),
        "status": str(job.get("status", "")),
        "created_at": str(job.get("created_at", "")),
        "completed_at": job.get("completed_at"),
    }


def _read_recorded_disposition(repo_root: Path) -> dict[str, object] | None:
    path = repo_root / PAPER_OBSERVATION_DISPOSITION_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_json_artifact(repo_root: Path, relative_path: str) -> dict[str, object] | None:
    path = _safe_artifact_path(repo_root, relative_path)
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_jsonl_artifact(repo_root: Path, relative_path: str) -> list[dict[str, object]]:
    path = _safe_artifact_path(repo_root, relative_path)
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


def _safe_artifact_path(repo_root: Path, relative_path: str) -> Path | None:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts or not relative_path:
        return None
    absolute = (repo_root / path).resolve()
    try:
        absolute.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return absolute


def _alert(severity: str, title: str, message: str, hint: str) -> dict[str, object]:
    return {
        "severity": severity,
        "title": title,
        "message": message,
        "hint": hint,
    }


def _int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string_mapping(value: Mapping[str, object]) -> dict[str, str]:
    return {str(key): "" if item is None else str(item) for key, item in value.items()}
