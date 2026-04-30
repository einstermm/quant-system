"""Append-only audit log for web write operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.web_api.state_db import record_audit_db_event
from apps.web_api.status import REPO_ROOT

AUDIT_LOG_PATH = Path("reports/web_reviews/audit_log.jsonl")


def record_audit_event(
    *,
    event_type: str,
    target: str,
    payload: dict[str, Any] | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    event = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "event_type": event_type,
        "target": target,
        "payload": payload or {},
    }
    path = repo_root / AUDIT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True))
        handle.write("\n")
    record_audit_db_event(event, repo_root=repo_root)
    return event


def read_audit_events(*, repo_root: Path = REPO_ROOT, limit: int = 200) -> dict[str, object]:
    path = repo_root / AUDIT_LOG_PATH
    rows: list[dict[str, object]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return {"path": str(AUDIT_LOG_PATH), "events": rows}
