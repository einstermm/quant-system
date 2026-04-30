"""Shared state helpers for paper readiness disposition records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from apps.web_api.status import REPO_ROOT


READINESS_DISPOSITION_PATH = Path("reports/web_reviews/paper_readiness_disposition.json")


def read_recorded_disposition(repo_root: Path = REPO_ROOT) -> dict[str, object] | None:
    path = repo_root / READINESS_DISPOSITION_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def disposition_resolution(
    recorded: Mapping[str, object] | None,
    current_candidate: Mapping[str, object] | None,
) -> dict[str, object]:
    if not recorded:
        return {
            "resolution_status": "none",
            "recorded_candidate_job_id": "",
            "current_candidate_job_id": _candidate_job_id(current_candidate),
            "superseded_by_candidate_job_id": "",
            "message": "",
        }

    recorded_candidate_job_id = str(recorded.get("candidate_job_id", "")).strip()
    current_candidate_job_id = _candidate_job_id(current_candidate)
    decision_id = str(recorded.get("decision_id", ""))
    if recorded_candidate_job_id and current_candidate_job_id and recorded_candidate_job_id != current_candidate_job_id:
        return {
            "resolution_status": "superseded",
            "recorded_candidate_job_id": recorded_candidate_job_id,
            "current_candidate_job_id": current_candidate_job_id,
            "superseded_by_candidate_job_id": current_candidate_job_id,
            "message": "处置已被新的候选回测覆盖，可以重新生成 Paper 准入。",
        }
    if decision_id == "return_to_research":
        return {
            "resolution_status": "requires_new_candidate",
            "recorded_candidate_job_id": recorded_candidate_job_id,
            "current_candidate_job_id": current_candidate_job_id,
            "superseded_by_candidate_job_id": "",
            "message": "最近处置要求回到研究阶段更换候选；当前候选未变化，不能重复生成准入。",
        }
    return {
        "resolution_status": "active",
        "recorded_candidate_job_id": recorded_candidate_job_id,
        "current_candidate_job_id": current_candidate_job_id,
        "superseded_by_candidate_job_id": "",
        "message": "存在准入处置记录；确认修复完成后再重新生成 Paper 准入。",
    }


def enriched_recorded_disposition(
    recorded: Mapping[str, object] | None,
    current_candidate: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if not recorded:
        return None
    payload = dict(recorded)
    payload.update(disposition_resolution(recorded, current_candidate))
    return payload


def _candidate_job_id(candidate: Mapping[str, object] | None) -> str:
    if not candidate:
        return ""
    return str(candidate.get("job_id", "")).strip()
