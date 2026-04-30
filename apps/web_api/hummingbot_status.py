"""Read-only Hummingbot paper session monitoring payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

from apps.web_api.jobs import collect_job_records
from apps.web_api.jobs import latest_hummingbot_cli_direct_paper_install
from apps.web_api.status import REPO_ROOT
from packages.adapters.hummingbot.paper_session_control import SESSION_STATE_PATH


def build_hummingbot_paper_status(
    repo_root: Path = REPO_ROOT,
    jobs: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    state_path = repo_root / SESSION_STATE_PATH
    state = _read_json(state_path)
    event_log_path = _event_log_path(repo_root, str(state.get("event_log_host_path", "")))
    event_log = _event_log_summary(event_log_path)
    latest_control = _latest_job(collect_job_records(jobs, repo_root=repo_root), "run_hummingbot_paper_session_control")
    latest_install = latest_hummingbot_cli_direct_paper_install(repo_root)
    status = _status(state, event_log)
    return {
        "status": status,
        "state": state,
        "state_path": str(SESSION_STATE_PATH),
        "state_exists": state_path.exists(),
        "event_log": event_log,
        "latest_control_job": latest_control,
        "latest_install_job": latest_install,
        "process_started_by_web": False,
        "live_order_submission_exposed": False,
        "recommended_actions": _recommended_actions(status, event_log),
    }


def _status(state: Mapping[str, object], event_log: Mapping[str, object]) -> str:
    state_status = str(state.get("status", ""))
    if not state_status:
        return "not_started"
    if state_status == "started_pending_event_collection":
        return "observing" if int(event_log.get("line_count", 0) or 0) > 0 else "started_no_events"
    if state_status == "stopped_pending_export_acceptance":
        return "stopped_pending_acceptance"
    return state_status


def _recommended_actions(status: str, event_log: Mapping[str, object]) -> list[str]:
    if status == "not_started":
        return ["Install Hummingbot paper files, then generate a start plan."]
    if status == "started_no_events":
        return ["Confirm the Hummingbot container is running and writing the configured event JSONL."]
    if status == "observing":
        return ["Continue monitoring until the paper session completes, then generate a stop plan."]
    if status == "stopped_pending_acceptance":
        if bool(event_log.get("exists")):
            return ["Run Hummingbot Export Acceptance using the recorded event JSONL."]
        return ["The session is stopped but the event JSONL is missing; inspect Hummingbot logs before acceptance."]
    return ["Review the latest paper session control job."]


def _event_log_path(repo_root: Path, value: str) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo_root / path


def _event_log_summary(path: Path | None) -> dict[str, object]:
    if path is None:
        return {
            "path": "",
            "exists": False,
            "size_bytes": 0,
            "line_count": 0,
            "parse_errors": 0,
            "first_event_type": "",
            "first_timestamp": "",
            "last_event_type": "",
            "last_timestamp": "",
        }
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "size_bytes": 0,
            "line_count": 0,
            "parse_errors": 0,
            "first_event_type": "",
            "first_timestamp": "",
            "last_event_type": "",
            "last_timestamp": "",
        }
    first: dict[str, object] = {}
    last: dict[str, object] = {}
    parse_errors = 0
    line_count = 0
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            line_count += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            if isinstance(event, dict):
                if not first:
                    first = event
                last = event
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "line_count": line_count,
        "parse_errors": parse_errors,
        "first_event_type": str(first.get("event_type", "")),
        "first_timestamp": str(first.get("timestamp", "")),
        "last_event_type": str(last.get("event_type", "")),
        "last_timestamp": str(last.get("timestamp", "")),
    }


def _latest_job(jobs: list[dict[str, object]], action_id: str) -> dict[str, object]:
    for job in jobs:
        if str(job.get("action_id", "")) == action_id:
            return {
                "job_id": str(job.get("job_id", "")),
                "status": str(job.get("status", "")),
                "created_at": str(job.get("created_at", "")),
                "artifacts": job.get("artifacts", {}) if isinstance(job.get("artifacts"), dict) else {},
                "parameters": job.get("parameters", {}) if isinstance(job.get("parameters"), dict) else {},
            }
    return {}


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
