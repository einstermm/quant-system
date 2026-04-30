"""Install generated Hummingbot CLI direct paper files into a local mount."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.cli_direct_paper_handoff import SCRIPT_NAME
from packages.adapters.hummingbot.cli_direct_paper_handoff import load_json
from packages.adapters.hummingbot.cli_paper_handoff import _write_json, _write_text
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class CliDirectPaperInstallResult:
    decision: str
    generated_at: datetime
    session_id: str
    handoff_json: str
    hummingbot_root: str
    dry_run: bool
    overwrite: bool
    clean_event_log: bool
    source_files: dict[str, str]
    install_targets: dict[str, str]
    file_results: dict[str, dict[str, str]]
    summary: dict[str, object]
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "handoff_json": self.handoff_json,
            "hummingbot_root": self.hummingbot_root,
            "dry_run": self.dry_run,
            "overwrite": self.overwrite,
            "clean_event_log": self.clean_event_log,
            "source_files": self.source_files,
            "install_targets": self.install_targets,
            "file_results": self.file_results,
            "summary": self.summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot CLI Direct Paper Install",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Hummingbot root: `{self.hummingbot_root}`",
            f"- Dry run: `{self.dry_run}`",
            f"- Overwrite: `{self.overwrite}`",
            f"- Clean event log: `{self.clean_event_log}`",
            "",
            "## File Results",
            "",
        ]
        for name, result in self.file_results.items():
            lines.append(f"- {name}: `{result.get('status', '')}` -> `{result.get('target', '')}`")
        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(f"- `{alert.severity}` {alert.title}: {alert.message}" for alert in self.alerts)
        else:
            lines.append("- None")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def install_cli_direct_paper_files(
    *,
    handoff: dict[str, Any],
    handoff_json: str | Path,
    output_dir: str | Path,
    source_root: str | Path,
    session_id: str,
    hummingbot_root: str | Path,
    dry_run: bool = False,
    overwrite: bool = False,
    clean_event_log: bool = False,
) -> CliDirectPaperInstallResult:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    root = Path(hummingbot_root)
    source_files = _source_files(handoff, Path(source_root))
    install_targets = _install_targets(handoff, root)
    alerts: list[Alert] = []
    file_results: dict[str, dict[str, str]] = {}

    if str(handoff.get("decision", "")) == "blocked":
        alerts.append(critical_alert("Handoff blocked", "Cannot install files from a blocked direct paper handoff."))

    for name in ("script_source", "script_config"):
        source = Path(source_files.get(name, ""))
        target = Path(install_targets.get(name, ""))
        result, item_alerts = _plan_or_copy_file(
            source=source,
            target=target,
            dry_run=dry_run,
            overwrite=overwrite,
            blocked=any(alert.severity == "CRITICAL" for alert in alerts),
        )
        file_results[name] = result
        alerts.extend(item_alerts)

    event_log_target = Path(install_targets.get("event_log_host_path", ""))
    event_result, event_alerts = _handle_event_log(
        event_log_target,
        dry_run=dry_run,
        clean_event_log=clean_event_log,
        blocked=any(alert.severity == "CRITICAL" for alert in alerts),
    )
    file_results["event_log_host_path"] = event_result
    alerts.extend(event_alerts)
    alerts.append(info_alert("Paper-only file install", "Installed files are for Hummingbot paper mode; no Hummingbot process was started."))

    decision = _decision(alerts=alerts, dry_run=dry_run)
    artifacts = {
        "install_report_json": str(output_path / "install_report.json"),
        "install_report_md": str(output_path / "install_report.md"),
    }
    result = CliDirectPaperInstallResult(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        handoff_json=str(handoff_json),
        hummingbot_root=str(root),
        dry_run=dry_run,
        overwrite=overwrite,
        clean_event_log=clean_event_log,
        source_files=source_files,
        install_targets=install_targets,
        file_results=file_results,
        summary=_summary(file_results),
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision),
        artifacts=artifacts,
    )
    _write_json(result.to_dict(), output_path / "install_report.json")
    _write_text(result.to_markdown(), output_path / "install_report.md")
    return result


def load_handoff(path: str | Path) -> dict[str, Any]:
    return load_json(path)


def _source_files(handoff: dict[str, Any], source_root: Path) -> dict[str, str]:
    artifacts = handoff.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    return {
        "script_source": str(_resolve_path(source_root, str(artifacts.get("script_source", "")))),
        "script_config": str(_resolve_path(source_root, str(artifacts.get("script_config", "")))),
    }


def _install_targets(handoff: dict[str, Any], hummingbot_root: Path) -> dict[str, str]:
    install_targets = handoff.get("install_targets", {})
    if not isinstance(install_targets, dict):
        install_targets = {}
    script_config_name = Path(str(install_targets.get("script_config", "script_config.yml"))).name
    event_log_name = Path(str(install_targets.get("event_log_host_path", "quant_system_web_hummingbot_events.jsonl"))).name
    return {
        "script_source": str(hummingbot_root / "scripts" / SCRIPT_NAME),
        "script_config": str(hummingbot_root / "conf" / "scripts" / script_config_name),
        "event_log_host_path": str(hummingbot_root / "data" / event_log_name),
    }


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _plan_or_copy_file(
    *,
    source: Path,
    target: Path,
    dry_run: bool,
    overwrite: bool,
    blocked: bool,
) -> tuple[dict[str, str], list[Alert]]:
    alerts: list[Alert] = []
    if not source.exists():
        alerts.append(critical_alert("Install source missing", f"Missing generated source file: {source}"))
        return _file_result(source, target, "missing_source"), alerts
    if blocked:
        return _file_result(source, target, "blocked"), alerts
    if target.exists() and target.read_bytes() != source.read_bytes() and not overwrite:
        alerts.append(critical_alert("Install target differs", f"Target exists and differs; enable overwrite to replace: {target}"))
        return _file_result(source, target, "target_differs"), alerts
    if dry_run:
        return _file_result(source, target, "planned"), alerts
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == source.read_bytes():
        return _file_result(source, target, "unchanged"), alerts
    shutil.copyfile(source, target)
    return _file_result(source, target, "installed"), alerts


def _handle_event_log(
    target: Path,
    *,
    dry_run: bool,
    clean_event_log: bool,
    blocked: bool,
) -> tuple[dict[str, str], list[Alert]]:
    alerts: list[Alert] = []
    if blocked:
        return {"target": str(target), "status": "blocked"}, alerts
    if not target.exists():
        return {"target": str(target), "status": "absent"}, alerts
    if not clean_event_log:
        alerts.append(warning_alert("Existing event log", f"Existing event log was left in place: {target}"))
        return {"target": str(target), "status": "exists"}, alerts
    if dry_run:
        return {"target": str(target), "status": "clean_planned"}, alerts
    target.unlink()
    return {"target": str(target), "status": "cleaned"}, alerts


def _file_result(source: Path, target: Path, status: str) -> dict[str, str]:
    return {"source": str(source), "target": str(target), "status": status}


def _decision(*, alerts: list[Alert], dry_run: bool) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "cli_direct_paper_install_blocked"
    if dry_run:
        return "cli_direct_paper_install_plan_ready"
    if any(alert.severity == "WARN" for alert in alerts):
        return "cli_direct_paper_files_installed_with_warnings"
    return "cli_direct_paper_files_installed"


def _summary(file_results: dict[str, dict[str, str]]) -> dict[str, object]:
    statuses = [result.get("status", "") for result in file_results.values()]
    return {
        "files": len(file_results),
        "installed": statuses.count("installed"),
        "unchanged": statuses.count("unchanged"),
        "planned": statuses.count("planned") + statuses.count("clean_planned"),
        "blocked": statuses.count("blocked") + statuses.count("missing_source") + statuses.count("target_differs"),
        "event_log_status": file_results.get("event_log_host_path", {}).get("status", ""),
    }


def _recommended_actions(decision: str) -> tuple[str, ...]:
    if decision == "cli_direct_paper_install_blocked":
        return ("Resolve install alerts and rerun the install job.", "Do not start Hummingbot until files are installed cleanly.")
    if decision == "cli_direct_paper_install_plan_ready":
        return ("Review install targets, then rerun with dry_run=false.",)
    return (
        "Start Hummingbot paper mode with the installed script config.",
        "After the paper session, run Hummingbot Export Acceptance on the event JSONL.",
    )
