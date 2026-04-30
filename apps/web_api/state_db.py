"""SQLite mirror for key web state documents."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from apps.web_api.status import REPO_ROOT

WEB_STATE_DB_PATH = Path("data/web_state.sqlite")


def initialize_state_db(*, repo_root: Path = REPO_ROOT) -> Path:
    db_path = repo_root / WEB_STATE_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS state_documents (
                key TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                target TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.commit()
    return db_path


def record_state_document(
    *,
    key: str,
    source_path: str,
    payload: Mapping[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    if not key.strip():
        raise ValueError("state document key is required")
    db_path = initialize_state_db(repo_root=repo_root)
    updated_at = datetime.now(tz=UTC).isoformat()
    payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO state_documents (key, source_path, updated_at, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                source_path=excluded.source_path,
                updated_at=excluded.updated_at,
                payload_json=excluded.payload_json
            """,
            (key, source_path, updated_at, payload_json),
        )
        connection.commit()
    return {"key": key, "source_path": source_path, "updated_at": updated_at}


def record_audit_db_event(
    event: Mapping[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    db_path = initialize_state_db(repo_root=repo_root)
    timestamp = str(event.get("timestamp", "")) or datetime.now(tz=UTC).isoformat()
    event_type = str(event.get("event_type", ""))
    target = str(event.get("target", ""))
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    with closing(sqlite3.connect(db_path)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO audit_events (timestamp, event_type, target, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                timestamp,
                event_type,
                target,
                json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str),
            ),
        )
        audit_id = int(cursor.lastrowid or 0)
        connection.commit()
    return {"id": audit_id, "timestamp": timestamp, "event_type": event_type, "target": target}


def build_state_db_status(*, repo_root: Path = REPO_ROOT) -> dict[str, object]:
    db_path = initialize_state_db(repo_root=repo_root)
    with closing(sqlite3.connect(db_path)) as connection:
        documents = [
            {
                "key": row[0],
                "source_path": row[1],
                "updated_at": row[2],
            }
            for row in connection.execute(
                "SELECT key, source_path, updated_at FROM state_documents ORDER BY updated_at DESC"
            )
        ]
        document_count = int(
            connection.execute("SELECT COUNT(*) FROM state_documents").fetchone()[0]
        )
        audit_event_count = int(connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0])
        latest_audit_at = connection.execute("SELECT MAX(timestamp) FROM audit_events").fetchone()[0]
    return {
        "path": str(WEB_STATE_DB_PATH),
        "database_ready": db_path.exists(),
        "tables": ["state_documents", "audit_events"],
        "document_count": document_count,
        "audit_event_count": audit_event_count,
        "latest_audit_at": latest_audit_at or "",
        "documents": documents,
    }
