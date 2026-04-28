"""Local Hummingbot runtime preflight checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert

SECRET_FIELD_MARKERS = (
    "api_key",
    "api_secret",
    "secret",
    "password",
    "passphrase",
    "private_key",
    "token",
)

PAPER_CONNECTOR_MARKERS = ("paper_trade", "mock_paper", "paper")
TESTNET_CONNECTOR_MARKERS = ("testnet", "sandbox")
CONNECTOR_SUFFIXES = (".yml", ".yaml")


@dataclass(frozen=True, slots=True)
class ConnectorConfigFinding:
    path: str
    account_id: str
    connector: str
    connector_risk: str
    secret_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "account_id": self.account_id,
            "connector": self.connector,
            "connector_risk": self.connector_risk,
            "secret_fields": list(self.secret_fields),
            "secret_values_redacted": True,
        }


@dataclass(frozen=True, slots=True)
class HummingbotRuntimePreflightResult:
    decision: str
    generated_at: datetime
    session_id: str
    expected_connector: str
    scan_roots: tuple[str, ...]
    connector_configs: tuple[ConnectorConfigFinding, ...]
    paper_trade_connectors: tuple[str, ...]
    alerts: tuple[Alert, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "expected_connector": self.expected_connector,
            "scan_roots": list(self.scan_roots),
            "connector_configs": [finding.to_dict() for finding in self.connector_configs],
            "paper_trade_connectors": list(self.paper_trade_connectors),
            "alerts": [alert.to_dict() for alert in self.alerts],
            "recommended_actions": list(self.recommended_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Hummingbot Runtime Preflight",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Expected connector: `{self.expected_connector}`",
            "",
            "## Scan Roots",
            "",
        ]
        lines.extend(f"- `{root}`" for root in self.scan_roots)
        lines.extend(["", "## Connector Configs", ""])
        if self.connector_configs:
            lines.append("| Account | Connector | Risk | Secret Fields | Path |")
            lines.append("| --- | --- | --- | --- | --- |")
            for finding in self.connector_configs:
                secret_fields = ", ".join(finding.secret_fields) if finding.secret_fields else "none"
                lines.append(
                    f"| `{finding.account_id}` | `{finding.connector}` | "
                    f"`{finding.connector_risk}` | `{secret_fields}` | `{finding.path}` |"
                )
        else:
            lines.append("- No connector credential config files found.")

        lines.extend(["", "## Paper Trade Connectors", ""])
        if self.paper_trade_connectors:
            lines.extend(f"- `{connector}`" for connector in self.paper_trade_connectors)
        else:
            lines.append("- No paper trade connectors found in conf_client.yml.")

        lines.extend(["", "## Alerts", ""])
        if self.alerts:
            lines.extend(
                f"- `{alert.severity}` {alert.title}: {alert.message}"
                for alert in self.alerts
            )
        else:
            lines.append("- None")
        lines.extend(["", "## Recommended Actions", ""])
        lines.extend(f"- {action}" for action in self.recommended_actions)
        lines.append("")
        return "\n".join(lines)


def build_runtime_preflight(
    *,
    scan_roots: Iterable[str | Path],
    session_id: str,
    expected_connector: str = "binance_paper_trade",
) -> HummingbotRuntimePreflightResult:
    root_paths = tuple(Path(root).expanduser() for root in scan_roots)
    connector_configs = tuple(
        parse_connector_config(path)
        for path in discover_connector_config_files(root_paths)
    )
    paper_trade_connectors = discover_paper_trade_connectors(root_paths)
    alerts = _build_alerts(
        connector_configs=connector_configs,
        paper_trade_connectors=paper_trade_connectors,
        expected_connector=expected_connector,
        scan_roots=root_paths,
    )
    decision = _decision(alerts)
    return HummingbotRuntimePreflightResult(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        expected_connector=expected_connector,
        scan_roots=tuple(str(root) for root in root_paths),
        connector_configs=connector_configs,
        paper_trade_connectors=paper_trade_connectors,
        alerts=tuple(alerts),
        recommended_actions=_recommended_actions(decision),
    )


def discover_connector_config_files(scan_roots: Iterable[Path]) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for root in scan_roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() in CONNECTOR_SUFFIXES:
            candidates.add(root)
            continue
        if not root.is_dir():
            continue
        for pattern in (
            "credentials/*/connectors/*.yml",
            "credentials/*/connectors/*.yaml",
            "conf/connectors/*.yml",
            "conf/connectors/*.yaml",
            "connectors/*.yml",
            "connectors/*.yaml",
            "**/credentials/*/connectors/*.yml",
            "**/credentials/*/connectors/*.yaml",
        ):
            candidates.update(path for path in root.glob(pattern) if path.is_file())
    return tuple(sorted(candidates, key=lambda path: str(path)))


def parse_connector_config(path: str | Path) -> ConnectorConfigFinding:
    config_path = Path(path)
    fields = _parse_yaml_like_fields(config_path)
    connector = fields.get("connector", config_path.stem)
    secret_fields = tuple(
        sorted(
            key
            for key in fields
            if any(marker in key.lower() for marker in SECRET_FIELD_MARKERS)
        )
    )
    return ConnectorConfigFinding(
        path=str(config_path),
        account_id=_account_id(config_path),
        connector=connector,
        connector_risk=_connector_risk(connector),
        secret_fields=secret_fields,
    )


def discover_paper_trade_connectors(scan_roots: Iterable[Path]) -> tuple[str, ...]:
    connectors: set[str] = set()
    for path in discover_conf_client_files(scan_roots):
        for exchange in _parse_paper_trade_exchanges(path):
            connectors.add(f"{exchange}_paper_trade")
    return tuple(sorted(connectors))


def discover_conf_client_files(scan_roots: Iterable[Path]) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for root in scan_roots:
        if not root.exists():
            continue
        if root.is_file() and root.name == "conf_client.yml":
            candidates.add(root)
            continue
        if not root.is_dir():
            continue
        for pattern in (
            "conf_client.yml",
            "conf/conf_client.yml",
            "credentials/*/conf_client.yml",
            "**/credentials/*/conf_client.yml",
        ):
            candidates.update(path for path in root.glob(pattern) if path.is_file())
    return tuple(sorted(candidates, key=lambda path: str(path)))


def write_runtime_preflight_json(
    result: HummingbotRuntimePreflightResult,
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_runtime_preflight_markdown(
    result: HummingbotRuntimePreflightResult,
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return output_path


def _parse_yaml_like_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def _parse_paper_trade_exchanges(path: Path) -> tuple[str, ...]:
    exchanges: list[str] = []
    in_paper_trade_exchanges = False
    list_indent = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "paper_trade_exchanges:":
            in_paper_trade_exchanges = True
            list_indent = len(line) - len(line.lstrip())
            continue
        if not in_paper_trade_exchanges:
            continue
        indent = len(line) - len(line.lstrip())
        if stripped.startswith("-"):
            value = stripped[1:].strip().strip("\"'")
            if value:
                exchanges.append(value)
            continue
        if indent <= list_indent:
            break
    return tuple(exchanges)


def _account_id(path: Path) -> str:
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "credentials" and index + 1 < len(parts):
            return parts[index + 1]
    return "unknown"


def _connector_risk(connector: str) -> str:
    normalized = connector.lower()
    if any(marker in normalized for marker in PAPER_CONNECTOR_MARKERS):
        return "paper"
    if any(marker in normalized for marker in TESTNET_CONNECTOR_MARKERS):
        return "testnet"
    if normalized:
        return "live"
    return "unknown"


def _build_alerts(
    *,
    connector_configs: tuple[ConnectorConfigFinding, ...],
    paper_trade_connectors: tuple[str, ...],
    expected_connector: str,
    scan_roots: tuple[Path, ...],
) -> list[Alert]:
    alerts: list[Alert] = []
    missing_roots = [str(root) for root in scan_roots if not root.exists()]
    if missing_roots:
        alerts.append(warning_alert("Scan root missing", f"Missing scan roots: {', '.join(missing_roots)}."))

    live_connectors = [
        finding
        for finding in connector_configs
        if finding.connector_risk == "live"
    ]
    for finding in live_connectors:
        alerts.append(
            critical_alert(
                "Live connector config present",
                f"Found live connector {finding.connector} in account {finding.account_id}; remove it before Phase 5 sandbox startup.",
            )
        )
        if finding.secret_fields:
            alerts.append(
                critical_alert(
                    "Live connector secret fields present",
                    f"{finding.connector} contains credential fields {', '.join(finding.secret_fields)}; values are redacted.",
                )
            )

    paper_or_testnet = [
        finding
        for finding in connector_configs
        if finding.connector_risk in {"paper", "testnet"}
    ]
    if not paper_or_testnet and not paper_trade_connectors:
        alerts.append(
            warning_alert(
                "No paper or testnet connector config",
                "No paper/testnet connector credential file or paper_trade exchange setting was found in the scanned Hummingbot mounts.",
            )
        )

    if expected_connector and expected_connector not in paper_trade_connectors and not any(
        finding.connector == expected_connector for finding in connector_configs
    ):
        alerts.append(
            warning_alert(
                "Expected connector not configured",
                f"Expected connector {expected_connector} was not found in connector credential files or paper_trade settings.",
            )
        )

    alerts.append(
        info_alert(
            "Secrets redacted",
            "Preflight reports connector field names only; credential values are never emitted.",
        )
    )
    return alerts


def _decision(alerts: list[Alert]) -> str:
    if any(alert.severity == "CRITICAL" for alert in alerts):
        return "blocked"
    if any(alert.severity == "WARN" for alert in alerts):
        return "runtime_ready_with_warnings"
    return "runtime_ready"


def _recommended_actions(decision: str) -> tuple[str, ...]:
    if decision == "blocked":
        return (
            "Do not start hummingbot-api or Hummingbot with the current credential mounts.",
            "Move live connector files out of mounted credentials/connectors directories or use a separate paper-only Hummingbot account.",
            "Configure only paper/testnet connectors for Phase 5, then rerun this runtime preflight.",
            "Keep LIVE_TRADING_ENABLED=false and GLOBAL_KILL_SWITCH=true.",
        )
    return (
        "Start only a sandbox or paper-mode Hummingbot session.",
        "Capture Hummingbot submitted, filled, completed, canceled, failed, disconnect, order exception, and balance events as JSONL.",
        "Run Phase 5.4 export acceptance on the captured event JSONL before extending the session.",
        "Keep live trading disabled.",
    )
