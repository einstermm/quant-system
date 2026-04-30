"""Persistent lightweight schedule registry for safe web actions."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from apps.web_api.state_db import record_state_document
from apps.web_api.status import REPO_ROOT

SCHEDULE_REGISTRY_PATH = Path("reports/web_reviews/web_schedules.json")


def list_schedules(repo_root: Path = REPO_ROOT) -> dict[str, object]:
    schedules = _read(repo_root)
    return {
        "registry_path": str(SCHEDULE_REGISTRY_PATH),
        "scheduler_worker_running": False,
        "schedules": schedules,
    }


def upsert_schedule(
    *,
    action_id: str,
    interval_minutes: int,
    enabled: bool,
    parameters: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive")
    schedules = [item for item in _read(repo_root) if str(item.get("action_id", "")) != action_id]
    now = datetime.now(tz=UTC)
    record = {
        "action_id": action_id,
        "interval_minutes": interval_minutes,
        "enabled": enabled,
        "parameters": parameters,
        "updated_at": now.isoformat(),
        "next_run_at": (now + timedelta(minutes=interval_minutes)).isoformat() if enabled else "",
    }
    schedules.append(record)
    path = repo_root / SCHEDULE_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schedules": schedules}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    record_state_document(
        key="web_schedules",
        source_path=str(SCHEDULE_REGISTRY_PATH),
        payload=payload,
        repo_root=repo_root,
    )
    return record


def _read(repo_root: Path) -> list[dict[str, object]]:
    path = repo_root / SCHEDULE_REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    schedules = payload.get("schedules")
    return [item for item in schedules if isinstance(item, dict)] if isinstance(schedules, list) else []
