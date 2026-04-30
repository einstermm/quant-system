"""Structured parameter scan summaries for the research workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from apps.web_api.equivalence import annotate_metric_equivalence
from apps.web_api.jobs import JobRecord
from apps.web_api.jobs import collect_job_records
from apps.web_api.status import REPO_ROOT


MAX_SCAN_ITEMS = 10
MAX_RECOMMENDATIONS = 8


def list_parameter_scans(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    scans: list[dict[str, object]] = []
    for job in collect_job_records(runtime_jobs, repo_root=repo_root):
        if str(job.get("action_id", "")) != "run_parameter_scan":
            continue
        item = _parameter_scan_item(job, repo_root)
        if item is not None:
            scans.append(item)
    limited = scans[:MAX_SCAN_ITEMS]
    return {
        "scans": limited,
        "latest_scan": limited[0] if limited else None,
    }


def _parameter_scan_item(job: Mapping[str, object], repo_root: Path) -> dict[str, object] | None:
    artifacts = _mapping(job.get("artifacts"))
    data = _load_json_artifact(repo_root, artifacts, "parameter_scan_json")
    if data is None:
        return None
    runs = data.get("runs")
    run_items = [_scan_run_item(run) for run in runs[:MAX_RECOMMENDATIONS]] if isinstance(runs, list) else []
    run_items = [item for item in run_items if item is not None]
    run_items = annotate_metric_equivalence(run_items, id_key="run_id")
    best_run = _scan_run_item(_mapping(data.get("best_run")))
    if best_run is not None:
        for item in run_items:
            if item.get("run_id") == best_run.get("run_id"):
                best_run["equivalence"] = item.get("equivalence")
                break
    return {
        "job_id": str(job.get("job_id", "")),
        "status": str(job.get("status", "")),
        "created_at": str(job.get("created_at", "")),
        "completed_at": job.get("completed_at"),
        "strategy_id": str(data.get("strategy_id", "")),
        "experiment_id": str(data.get("experiment_id", "")),
        "artifact_path": str(artifacts.get("parameter_scan_json", "")),
        "summary_csv_path": str(artifacts.get("parameter_scan_csv", "")),
        "selection_policy": _string_mapping(_mapping(data.get("selection_policy"))),
        "run_count": len(runs) if isinstance(runs, list) else 0,
        "best_run": best_run,
        "recommendations": run_items,
    }


def _scan_run_item(value: Mapping[str, object]) -> dict[str, object] | None:
    run_id = str(value.get("run_id", "")).strip()
    if not run_id:
        return None
    rank = value.get("rank")
    return {
        "rank": rank,
        "run_id": run_id,
        "parameters": _string_mapping(_mapping(value.get("parameters"))),
        "metrics": _string_mapping(_mapping(value.get("metrics"))),
        "recommendation": "best" if str(rank) == "1" else "ranked",
    }


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
    return {str(key): "" if item is None else str(item) for key, item in value.items()}
