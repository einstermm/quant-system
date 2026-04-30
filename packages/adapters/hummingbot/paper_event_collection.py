"""Collect Hummingbot paper event JSONL into the quant-system report tree."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.cli_paper_handoff import _write_json, _write_text
from packages.adapters.hummingbot.paper_session_control import SESSION_STATE_PATH
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class PaperEventCollectionResult:
    decision: str
    generated_at: datetime
    session_id: str
    source_path: str
    events_jsonl: str
    summary: dict[str, object]
    alerts: tuple[Alert, ...]
    artifacts: dict[str, str]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "source_path": self.source_path,
            "events_jsonl": self.events_jsonl,
            "summary": self.summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "artifacts": self.artifacts,
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Paper Event Collection",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Source: `{self.source_path}`",
            f"- Events JSONL: `{self.events_jsonl}`",
            f"- Events: `{self.summary.get('event_count', '')}`",
            f"- Parse errors: `{self.summary.get('parse_errors', '')}`",
            "",
            "## Event Types",
            "",
        ]
        event_types = self.summary.get("event_types", {})
        if isinstance(event_types, dict) and event_types:
            lines.extend(f"- {key}: `{value}`" for key, value in sorted(event_types.items()))
        else:
            lines.append("- None")
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def collect_paper_events(
    *,
    state_path: str | Path,
    output_dir: str | Path,
    source_path: str | Path | None,
    source_root: str | Path,
    session_id: str,
    max_lines: int = 50000,
) -> PaperEventCollectionResult:
    if max_lines <= 0:
        raise ValueError("max_lines must be positive")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    state = _read_json(Path(state_path))
    source = _source_path(state=state, source_path=source_path, source_root=Path(source_root))
    events_path = output_path / "events.jsonl"
    report_path = output_path / "collection_report.json"
    report_md_path = output_path / "collection_report.md"
    alerts: list[Alert] = []
    summary, valid_lines = _read_events(source, max_lines=max_lines, alerts=alerts)
    if valid_lines:
        events_path.write_text("".join(valid_lines), encoding="utf-8")
    else:
        events_path.write_text("", encoding="utf-8")
    alerts.append(info_alert("Events copied into web job", "Collected events are a local copy for acceptance; source Hummingbot files were not modified."))
    decision = _decision(alerts)
    artifacts = {
        "collection_report_json": str(report_path),
        "collection_report_md": str(report_md_path),
        "events_jsonl": str(events_path),
    }
    result = PaperEventCollectionResult(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        source_path=str(source) if source else "",
        events_jsonl=str(events_path),
        summary=summary,
        alerts=tuple(alerts),
        artifacts=artifacts,
        recommended_actions=_recommended_actions(decision),
    )
    _write_json(result.to_dict(), report_path)
    _write_text(result.to_markdown(), report_md_path)
    return result


def _source_path(*, state: dict[str, object], source_path: str | Path | None, source_root: Path) -> Path | None:
    value = str(source_path or "").strip()
    if not value or value == "auto_from_session_state":
        value = str(state.get("event_log_host_path", ""))
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else source_root / path


def _read_events(path: Path | None, *, max_lines: int, alerts: list[Alert]) -> tuple[dict[str, object], list[str]]:
    if path is None:
        alerts.append(critical_alert("Event source missing", "No source path was provided and session state has no event_log_host_path."))
        return _empty_summary(), []
    if not path.exists():
        alerts.append(critical_alert("Event source missing", f"Hummingbot event JSONL does not exist: {path}"))
        return {**_empty_summary(), "source_exists": False}, []
    event_types: Counter[str] = Counter()
    valid_lines: list[str] = []
    parse_errors = 0
    first: dict[str, Any] = {}
    last: dict[str, Any] = {}
    truncated = False
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if line_number > max_lines:
                truncated = True
                break
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            if not isinstance(event, dict):
                parse_errors += 1
                continue
            if not first:
                first = event
            last = event
            event_type = str(event.get("event_type", "unknown"))
            event_types[event_type] += 1
            valid_lines.append(json.dumps(event, sort_keys=True) + "\n")
    if not valid_lines:
        alerts.append(critical_alert("No valid events", f"No valid Hummingbot event JSONL lines were found in {path}."))
    if parse_errors:
        alerts.append(warning_alert("Event parse errors", f"Skipped {parse_errors} invalid JSONL line(s)."))
    if truncated:
        alerts.append(warning_alert("Event collection truncated", f"Stopped after max_lines={max_lines}."))
    return (
        {
            "source_exists": True,
            "source_size_bytes": path.stat().st_size,
            "event_count": len(valid_lines),
            "parse_errors": parse_errors,
            "truncated": truncated,
            "first_event_type": str(first.get("event_type", "")),
            "first_timestamp": str(first.get("timestamp", "")),
            "last_event_type": str(last.get("event_type", "")),
            "last_timestamp": str(last.get("timestamp", "")),
            "event_types": dict(event_types),
        },
        valid_lines,
    )


def _empty_summary() -> dict[str, object]:
    return {
        "source_exists": False,
        "source_size_bytes": 0,
        "event_count": 0,
        "parse_errors": 0,
        "truncated": False,
        "first_event_type": "",
        "first_timestamp": "",
        "last_event_type": "",
        "last_timestamp": "",
        "event_types": {},
    }


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "paper_event_collection_blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "paper_events_collected_with_warnings"
    return "paper_events_collected"


def _recommended_actions(decision: str) -> tuple[str, ...]:
    if decision == "paper_event_collection_blocked":
        return ("Confirm Hummingbot wrote the event JSONL and rerun collection.",)
    return ("Run Hummingbot Export Acceptance using the collected events_jsonl artifact.",)


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
