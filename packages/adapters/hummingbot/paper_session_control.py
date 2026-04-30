"""Generate and record Hummingbot CLI direct paper session control actions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.cli_direct_paper_handoff import SCRIPT_NAME
from packages.adapters.hummingbot.cli_paper_handoff import _write_json, _write_text
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert

SESSION_STATE_PATH = Path("reports/web_reviews/hummingbot_paper_session_state.json")
VALID_MODES = {"start_plan", "record_started", "stop_plan", "record_stopped"}


@dataclass(frozen=True, slots=True)
class PaperSessionControlResult:
    decision: str
    generated_at: datetime
    mode: str
    session_id: str
    container_name: str
    hummingbot_root: str
    script_config_name: str
    event_log_host_path: str
    start_command: str
    stop_command: str
    process_started_by_web: bool
    state: dict[str, object]
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "mode": self.mode,
            "session_id": self.session_id,
            "container_name": self.container_name,
            "hummingbot_root": self.hummingbot_root,
            "script_config_name": self.script_config_name,
            "event_log_host_path": self.event_log_host_path,
            "start_command": self.start_command,
            "stop_command": self.stop_command,
            "process_started_by_web": self.process_started_by_web,
            "state": self.state,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Paper Session Control",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Mode: `{self.mode}`",
            f"- Session id: `{self.session_id}`",
            f"- Container: `{self.container_name}`",
            f"- Hummingbot root: `{self.hummingbot_root}`",
            f"- Script config: `{self.script_config_name}`",
            f"- Event log: `{self.event_log_host_path}`",
            f"- Process started by Web: `{self.process_started_by_web}`",
            "",
            "## Start Command",
            "",
            "```bash",
            self.start_command,
            "```",
            "",
            "## Stop Command",
            "",
            "```bash",
            self.stop_command,
            "```",
            "",
            "## Alerts",
            "",
        ]
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def build_paper_session_control(
    *,
    install_report: dict[str, Any],
    output_dir: str | Path,
    state_path: str | Path,
    mode: str,
    session_id: str,
    container_name: str,
    hummingbot_image: str,
    operator_note: str = "",
) -> PaperSessionControlResult:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    state_file = Path(state_path)
    now = datetime.now(tz=UTC)
    alerts = _alerts_for_install(install_report)
    prior_state = _read_state(state_file)
    install_targets = _dict(install_report.get("install_targets"))
    hummingbot_root = str(install_report.get("hummingbot_root", ""))
    script_config_name = Path(str(install_targets.get("script_config", ""))).name
    event_log_host_path = str(install_targets.get("event_log_host_path", ""))
    if not script_config_name:
        alerts.append(critical_alert("Script config target missing", "Install report does not include script_config target."))
    if not event_log_host_path:
        alerts.append(critical_alert("Event log target missing", "Install report does not include event_log_host_path."))

    if mode in {"stop_plan", "record_stopped"} and str(prior_state.get("status", "")) != "started_pending_event_collection":
        alerts.append(warning_alert("No active session recorded", "Current state does not show a started Hummingbot paper session."))

    start_command = _start_command(
        hummingbot_root=hummingbot_root,
        hummingbot_image=hummingbot_image,
        container_name=container_name,
        script_config_name=script_config_name,
    )
    stop_command = f"docker stop {container_name}"
    decision = _decision(mode=mode, alerts=alerts)
    state = _state_payload(
        prior_state=prior_state,
        mode=mode,
        decision=decision,
        now=now,
        session_id=session_id,
        container_name=container_name,
        hummingbot_root=hummingbot_root,
        script_config_name=script_config_name,
        event_log_host_path=event_log_host_path,
        operator_note=operator_note,
    )
    artifacts = {
        "session_control_json": str(output_path / "session_control.json"),
        "session_control_md": str(output_path / "session_control.md"),
        "session_state_json": str(state_file),
    }
    result = PaperSessionControlResult(
        decision=decision,
        generated_at=now,
        mode=mode,
        session_id=session_id,
        container_name=container_name,
        hummingbot_root=hummingbot_root,
        script_config_name=script_config_name,
        event_log_host_path=event_log_host_path,
        start_command=start_command,
        stop_command=stop_command,
        process_started_by_web=False,
        state=state,
        alerts=tuple(alerts + [info_alert("Manual process control", "Web generated commands and state records only; it did not start Hummingbot.")]),
        recommended_actions=_recommended_actions(decision, mode),
        artifacts=artifacts,
    )
    _write_json(result.to_dict(), output_path / "session_control.json")
    _write_text(result.to_markdown(), output_path / "session_control.md")
    if mode in {"record_started", "record_stopped"} and not decision.endswith("blocked"):
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _alerts_for_install(install_report: dict[str, Any]) -> list[Alert]:
    alerts: list[Alert] = []
    decision = str(install_report.get("decision", ""))
    if decision == "cli_direct_paper_install_blocked":
        alerts.append(critical_alert("Install blocked", "Cannot control a paper session from a blocked install report."))
    if bool(install_report.get("dry_run", False)):
        alerts.append(critical_alert("Install was dry run", "Run file install with dry_run=false before starting Hummingbot."))
    summary = _dict(install_report.get("summary"))
    installed = _intish(summary.get("installed")) + _intish(summary.get("unchanged"))
    if installed < 2:
        alerts.append(critical_alert("Installed files missing", "Both script_source and script_config must be installed or unchanged."))
    return alerts


def _read_state(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _state_payload(
    *,
    prior_state: dict[str, object],
    mode: str,
    decision: str,
    now: datetime,
    session_id: str,
    container_name: str,
    hummingbot_root: str,
    script_config_name: str,
    event_log_host_path: str,
    operator_note: str,
) -> dict[str, object]:
    state = dict(prior_state)
    state.update(
        {
            "session_id": session_id,
            "container_name": container_name,
            "hummingbot_root": hummingbot_root,
            "script_config_name": script_config_name,
            "event_log_host_path": event_log_host_path,
            "last_decision": decision,
            "last_mode": mode,
            "updated_at": now.isoformat(),
            "operator_note": operator_note,
            "process_started_by_web": False,
        }
    )
    if mode == "start_plan":
        state["status"] = "start_plan_ready"
    elif mode == "record_started":
        state["status"] = "started_pending_event_collection"
        state["started_at"] = now.isoformat()
        state.pop("stopped_at", None)
    elif mode == "stop_plan":
        state["status"] = state.get("status", "stop_plan_ready")
    elif mode == "record_stopped":
        state["status"] = "stopped_pending_export_acceptance"
        state["stopped_at"] = now.isoformat()
    return state


def _decision(*, mode: str, alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "paper_session_control_blocked"
    return {
        "start_plan": "paper_session_start_plan_ready",
        "record_started": "paper_session_started_recorded",
        "stop_plan": "paper_session_stop_plan_ready",
        "record_stopped": "paper_session_stopped_recorded",
    }[mode]


def _start_command(
    *,
    hummingbot_root: str,
    hummingbot_image: str,
    container_name: str,
    script_config_name: str,
) -> str:
    return (
        f"cd {hummingbot_root} && "
        "read -rsp 'Hummingbot password: ' HBOT_PASSWORD; echo; "
        f"docker run --rm --name {container_name} "
        "-v \"$PWD/conf:/home/hummingbot/conf\" "
        "-v \"$PWD/conf/connectors:/home/hummingbot/conf/connectors\" "
        "-v \"$PWD/conf/scripts:/home/hummingbot/conf/scripts\" "
        "-v \"$PWD/data:/home/hummingbot/data\" "
        "-v \"$PWD/logs:/home/hummingbot/logs\" "
        "-v \"$PWD/scripts:/home/hummingbot/scripts\" "
        f"{hummingbot_image} "
        "/bin/bash -lc \"conda activate hummingbot && ./bin/hummingbot_quickstart.py "
        f"--headless --config-password \\\"$HBOT_PASSWORD\\\" --v2 {script_config_name}\""
    )


def _recommended_actions(decision: str, mode: str) -> tuple[str, ...]:
    if decision == "paper_session_control_blocked":
        return ("Fix install/session alerts before starting or stopping Hummingbot.",)
    if mode == "start_plan":
        return ("Run the generated start command manually.", "After it starts, record_started in Web.")
    if mode == "record_started":
        return ("Let Hummingbot paper mode produce the event JSONL.", "When the run is complete, generate a stop plan.")
    if mode == "stop_plan":
        return ("Run the generated stop command manually.", "After it stops, record_stopped in Web.")
    return ("Run Hummingbot Export Acceptance using the recorded event JSONL.",)


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _intish(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0
