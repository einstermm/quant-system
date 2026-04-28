"""Phase 6.3 live connector handoff and preflight."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from packages.adapters.hummingbot.runtime_preflight import (
    ConnectorConfigFinding,
    discover_connector_config_files,
    parse_connector_config,
)
from packages.backtesting.result import decimal_to_str
from packages.data.simple_yaml import load_simple_yaml
from packages.observability.alerts import Alert, critical_alert, info_alert, warning_alert


@dataclass(frozen=True, slots=True)
class LiveConnectorCheckItem:
    item_id: str
    title: str
    status: str
    details: str
    evidence: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "status": self.status,
            "details": self.details,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class LiveConnectorPreflightReport:
    decision: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    expected_connector: str
    market_type: str
    allowed_pairs: tuple[str, ...]
    connector_status: dict[str, object]
    checklist: tuple[LiveConnectorCheckItem, ...]
    risk_summary: dict[str, object]
    environment: dict[str, object]
    alerts: tuple[Alert, ...]
    runbook: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "expected_connector": self.expected_connector,
            "market_type": self.market_type,
            "allowed_pairs": list(self.allowed_pairs),
            "connector_status": self.connector_status,
            "checklist": [item.to_dict() for item in self.checklist],
            "risk_summary": _json_safe(self.risk_summary),
            "environment": self.environment,
            "alerts": [alert.to_dict() for alert in self.alerts],
            "runbook": list(self.runbook),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        required_fields = _string_list(self.connector_status["required_secret_fields"])
        missing_fields = _string_list(self.connector_status["missing_secret_fields"])
        missing_fields_text = ", ".join(missing_fields) or "none"
        lines = [
            "# Phase 6.3 Live Connector Preflight",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Connector: `{self.expected_connector}`",
            f"- Market type: `{self.market_type}`",
            f"- Allowed pairs: `{', '.join(self.allowed_pairs)}`",
            "",
            "## Connector Status",
            "",
            f"- Hummingbot root: `{self.connector_status['hummingbot_root']}`",
            f"- Host connector path: `{self.connector_status['expected_host_config_path']}`",
            "- Container connector path: "
            f"`{self.connector_status['expected_container_config_path']}`",
            "- Expected connector configured: "
            f"`{self.connector_status['expected_connector_configured']}`",
            f"- Required secret fields: `{', '.join(required_fields)}`",
            f"- Missing secret fields: `{missing_fields_text}`",
            f"- Secret values redacted: `{self.connector_status['secret_values_redacted']}`",
            "",
            "## Connector Configs",
            "",
        ]
        configs = self.connector_status["connector_configs"]
        if isinstance(configs, list) and configs:
            lines.append("| Account | Connector | Risk | Secret Fields | Path |")
            lines.append("| --- | --- | --- | --- | --- |")
            for config in configs:
                if not isinstance(config, dict):
                    continue
                fields = ", ".join(str(field) for field in config.get("secret_fields", []))
                fields = fields or "none"
                lines.append(
                    f"| `{config.get('account_id')}` | `{config.get('connector')}` | "
                    f"`{config.get('connector_risk')}` | `{fields}` | `{config.get('path')}` |"
                )
        else:
            lines.append("- No connector credential config files found.")

        lines.extend(["", "## Checklist", ""])
        lines.extend(
            f"- `{item.status}` {item.title}: {item.details}"
            + (f" Evidence: `{item.evidence}`" if item.evidence else "")
            for item in self.checklist
        )
        lines.extend(
            [
                "",
                "## Environment",
                "",
                f"- Live trading enabled: `{self.environment['live_trading_enabled']}`",
                f"- Global kill switch: `{self.environment['global_kill_switch']}`",
                f"- Alert channel configured: `{self.environment['alert_channel_configured']}`",
                f"- Exchange key env detected: `{self.environment['exchange_key_env_detected']}`",
                "",
                "## Alerts",
                "",
            ]
        )
        if self.alerts:
            lines.extend(
                f"- `{alert.severity}` {alert.title}: {alert.message}"
                for alert in self.alerts
            )
        else:
            lines.append("- None")

        lines.extend(["", "## Runbook", ""])
        lines.extend(f"- {step}" for step in self.runbook)
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_connector_preflight(
    *,
    activation_checklist: dict[str, Any],
    credential_allowlist: dict[str, Any],
    operator_signoff: dict[str, Any],
    live_risk_config: dict[str, Any],
    environment: dict[str, object],
    hummingbot_root: str | Path,
    session_id: str,
    strategy_id: str,
    expected_connector: str,
    market_type: str,
    allowed_pairs: Iterable[str],
    required_secret_fields: Iterable[str],
    artifacts: dict[str, str] | None = None,
) -> LiveConnectorPreflightReport:
    pair_tuple = tuple(allowed_pairs)
    secret_field_tuple = tuple(required_secret_fields)
    root = Path(hummingbot_root).expanduser()
    connector_configs = tuple(
        parse_connector_config(path) for path in discover_connector_config_files((root,))
    )
    matched_configs = _matched_connector_configs(connector_configs, expected_connector)
    unexpected_live_configs = tuple(
        config
        for config in connector_configs
        if config.connector_risk == "live" and config.connector != expected_connector
    )
    missing_secret_fields = _missing_secret_fields(matched_configs, secret_field_tuple)
    connector_status = _connector_status(
        root=root,
        expected_connector=expected_connector,
        connector_configs=connector_configs,
        matched_configs=matched_configs,
        unexpected_live_configs=unexpected_live_configs,
        required_secret_fields=secret_field_tuple,
        missing_secret_fields=missing_secret_fields,
    )
    risk_summary = _risk_summary(
        live_risk_config=live_risk_config,
        credential_allowlist=credential_allowlist,
        operator_signoff=operator_signoff,
    )
    checklist = _checklist(
        activation_checklist=activation_checklist,
        credential_allowlist=credential_allowlist,
        operator_signoff=operator_signoff,
        environment=environment,
        connector_status=connector_status,
        risk_summary=risk_summary,
        expected_connector=expected_connector,
        market_type=market_type,
        allowed_pairs=pair_tuple,
    )
    decision = _decision(checklist)
    alerts = _alerts(
        decision=decision,
        checklist=checklist,
        expected_connector=expected_connector,
        matched_configs=matched_configs,
        missing_secret_fields=missing_secret_fields,
    )
    return LiveConnectorPreflightReport(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=strategy_id,
        expected_connector=expected_connector,
        market_type=market_type,
        allowed_pairs=pair_tuple,
        connector_status=connector_status,
        checklist=tuple(checklist),
        risk_summary=risk_summary,
        environment=environment,
        alerts=tuple(alerts),
        runbook=_runbook(decision, root, expected_connector),
        artifacts=artifacts or {},
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_risk_config(path: str | Path) -> dict[str, Any]:
    return load_simple_yaml(path)


def write_live_connector_preflight_json(
    report: LiveConnectorPreflightReport,
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_live_connector_preflight_markdown(
    report: LiveConnectorPreflightReport,
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def default_required_secret_fields(connector: str) -> tuple[str, ...]:
    if connector == "binance":
        return ("binance_api_key", "binance_api_secret")
    normalized = connector.replace("-", "_")
    return (f"{normalized}_api_key", f"{normalized}_api_secret")


def _matched_connector_configs(
    connector_configs: tuple[ConnectorConfigFinding, ...],
    expected_connector: str,
) -> tuple[ConnectorConfigFinding, ...]:
    return tuple(
        config
        for config in connector_configs
        if config.connector == expected_connector or Path(config.path).stem == expected_connector
    )


def _missing_secret_fields(
    matched_configs: tuple[ConnectorConfigFinding, ...],
    required_secret_fields: tuple[str, ...],
) -> tuple[str, ...]:
    if not matched_configs:
        return required_secret_fields
    present = {field for config in matched_configs for field in config.secret_fields}
    return tuple(field for field in required_secret_fields if field not in present)


def _connector_status(
    *,
    root: Path,
    expected_connector: str,
    connector_configs: tuple[ConnectorConfigFinding, ...],
    matched_configs: tuple[ConnectorConfigFinding, ...],
    unexpected_live_configs: tuple[ConnectorConfigFinding, ...],
    required_secret_fields: tuple[str, ...],
    missing_secret_fields: tuple[str, ...],
) -> dict[str, object]:
    host_config_path = root / "conf" / "connectors" / f"{expected_connector}.yml"
    return {
        "hummingbot_root": str(root),
        "expected_host_config_path": str(host_config_path),
        "expected_container_config_path": (
            f"/home/hummingbot/conf/connectors/{expected_connector}.yml"
        ),
        "expected_connector_configured": bool(matched_configs),
        "expected_connector_configs": [config.to_dict() for config in matched_configs],
        "unexpected_live_connector_configs": [
            config.to_dict() for config in unexpected_live_configs
        ],
        "connector_configs": [config.to_dict() for config in connector_configs],
        "required_secret_fields": list(required_secret_fields),
        "missing_secret_fields": list(missing_secret_fields),
        "secret_values_redacted": True,
    }


def _risk_summary(
    *,
    live_risk_config: dict[str, Any],
    credential_allowlist: dict[str, Any],
    operator_signoff: dict[str, Any],
) -> dict[str, object]:
    expected_limits = _dict(operator_signoff.get("confirmed_limits"))
    credential_limits = _dict(credential_allowlist.get("accepted_live_risk_limits"))
    summary: dict[str, object] = {
        "expected_limits_source": "operator_signoff.confirmed_limits",
        "credential_limits_source": "credential_allowlist.accepted_live_risk_limits",
    }
    for key in (
        "max_order_notional",
        "max_symbol_notional",
        "max_gross_notional",
        "max_daily_loss",
        "max_drawdown_pct",
    ):
        live_value = live_risk_config.get(key)
        expected_value = expected_limits.get(key)
        credential_value = credential_limits.get(key)
        summary[f"{key}_live"] = str(live_value) if live_value is not None else ""
        summary[f"{key}_expected"] = str(expected_value) if expected_value is not None else ""
        summary[f"{key}_credential"] = str(credential_value) if credential_value is not None else ""
        summary[f"{key}_matches_operator_signoff"] = _decimal_equal(live_value, expected_value)
        if credential_value is not None:
            summary[f"{key}_matches_credential_review"] = _decimal_equal(
                live_value,
                credential_value,
            )
    return summary


def _checklist(
    *,
    activation_checklist: dict[str, Any],
    credential_allowlist: dict[str, Any],
    operator_signoff: dict[str, Any],
    environment: dict[str, object],
    connector_status: dict[str, object],
    risk_summary: dict[str, object],
    expected_connector: str,
    market_type: str,
    allowed_pairs: tuple[str, ...],
) -> list[LiveConnectorCheckItem]:
    first_live_allowlist = _dict(credential_allowlist.get("first_live_allowlist"))
    credential_pairs = tuple(
        str(pair)
        for pair in first_live_allowlist.get("trading_pairs", [])
    )
    operator_pairs = tuple(
        str(pair)
        for pair in _list(operator_signoff.get("first_live_allowlist"))
    )
    credential_connector = str(first_live_allowlist.get("connector", ""))
    credential_market_type = str(first_live_allowlist.get("market_type", ""))
    risk_matches = all(
        bool(risk_summary.get(f"{key}_matches_operator_signoff"))
        for key in (
            "max_order_notional",
            "max_symbol_notional",
            "max_gross_notional",
            "max_daily_loss",
            "max_drawdown_pct",
        )
    )
    return [
        _item(
            "phase_6_2_activation",
            "Phase 6.2 activation checklist ready",
            "PASS" if activation_checklist.get("decision") == "live_activation_ready" else "FAIL",
            f"Activation checklist decision is {activation_checklist.get('decision', 'unknown')}.",
        ),
        _item(
            "credential_allowlist",
            "Credential and exchange allowlist reviewed",
            "PASS"
            if credential_allowlist.get("decision") == "credential_allowlist_review_confirmed"
            else "FAIL",
            f"Credential review decision is {credential_allowlist.get('decision', 'unknown')}.",
        ),
        _item(
            "operator_signoff",
            "Operator signoff recorded",
            "PASS" if operator_signoff.get("decision") == "operator_signoff_confirmed" else "FAIL",
            f"Operator signoff decision is {operator_signoff.get('decision', 'unknown')}.",
        ),
        _item(
            "connector_scope",
            "Connector scope matches first live target",
            "PASS"
            if credential_connector == expected_connector and credential_market_type == market_type
            else "FAIL",
            (
                f"Credential review connector={credential_connector or 'unknown'}, "
                f"market_type={credential_market_type or 'unknown'}."
            ),
        ),
        _item(
            "symbol_allowlist",
            "First live symbol allowlist matches",
            "PASS"
            if credential_pairs == allowed_pairs and operator_pairs == allowed_pairs
            else "FAIL",
            (
                f"Credential pairs={credential_pairs or 'unknown'}; "
                f"operator pairs={operator_pairs or 'unknown'}."
            ),
        ),
        _item(
            "live_risk_config",
            "Live risk config matches operator signoff",
            "PASS" if risk_matches else "FAIL",
            "Strict live risk file must match the Phase 6.2 operator signoff.",
        ),
        _item(
            "unexpected_live_connectors",
            "No unexpected live connector configs mounted",
            "PASS" if not connector_status["unexpected_live_connector_configs"] else "FAIL",
            "Only the approved first-live connector may be mounted for Phase 6.3.",
        ),
        _item(
            "expected_connector_config",
            "Expected live connector config exists",
            "PASS" if connector_status["expected_connector_configured"] else "PENDING",
            "Configure this only inside Hummingbot CLI; values remain redacted.",
            str(connector_status["expected_host_config_path"]),
        ),
        _item(
            "connector_secret_fields",
            "Expected connector secret field names detected",
            _secret_field_status(connector_status),
            "The report records field names only and never emits credential values.",
        ),
        _item(
            "live_disabled",
            "Live trading remains disabled in quant-system",
            "PASS" if not bool(environment.get("live_trading_enabled")) else "FAIL",
            "LIVE_TRADING_ENABLED must remain false until the final live batch activation step.",
        ),
        _item(
            "kill_switch_enabled",
            "Global kill switch remains enabled",
            "PASS" if bool(environment.get("global_kill_switch")) else "FAIL",
            "GLOBAL_KILL_SWITCH must remain true before final live batch activation.",
        ),
        _item(
            "alert_channel",
            "External alert channel configured",
            "PASS" if bool(environment.get("alert_channel_configured")) else "FAIL",
            "At least one external alert channel must be configured before live connector use.",
        ),
        _item(
            "exchange_keys_not_in_quant_env",
            "Exchange keys are not stored in quant-system env",
            "PASS" if not bool(environment.get("exchange_key_env_detected")) else "FAIL",
            "Real exchange credentials belong in Hummingbot connector config.",
        ),
    ]


def _secret_field_status(connector_status: dict[str, object]) -> str:
    if not connector_status["expected_connector_configured"]:
        return "PENDING"
    if connector_status["missing_secret_fields"]:
        return "FAIL"
    return "PASS"


def _item(
    item_id: str,
    title: str,
    status: str,
    details: str,
    evidence: str = "",
) -> LiveConnectorCheckItem:
    return LiveConnectorCheckItem(
        item_id=item_id,
        title=title,
        status=status,
        details=details,
        evidence=evidence,
    )


def _decision(checklist: list[LiveConnectorCheckItem]) -> str:
    if any(item.status == "FAIL" for item in checklist):
        return "live_connector_preflight_blocked"
    if any(item.status == "PENDING" for item in checklist):
        return "live_connector_config_pending"
    if any(item.status == "WARN" for item in checklist):
        return "live_connector_preflight_ready_with_warnings"
    return "live_connector_preflight_ready"


def _alerts(
    *,
    decision: str,
    checklist: list[LiveConnectorCheckItem],
    expected_connector: str,
    matched_configs: tuple[ConnectorConfigFinding, ...],
    missing_secret_fields: tuple[str, ...],
) -> list[Alert]:
    alerts: list[Alert] = [
        info_alert(
            "Secrets redacted",
            "Phase 6.3 reports connector field names only; credential values are never emitted.",
        )
    ]
    if decision == "live_connector_config_pending":
        alerts.append(
            warning_alert(
            "Connector config pending",
            f"Configure {expected_connector} in Hummingbot CLI, then rerun Phase 6.3.",
            )
        )
    if matched_configs and missing_secret_fields:
        alerts.append(
            critical_alert(
                "Connector secret fields missing",
                f"Missing expected field names: {', '.join(missing_secret_fields)}.",
            )
        )
    for item in checklist:
        if item.status == "FAIL":
            alerts.append(critical_alert(item.title, item.details))
    return alerts


def _runbook(decision: str, hummingbot_root: Path, expected_connector: str) -> tuple[str, ...]:
    connector_path = hummingbot_root / "conf" / "connectors" / f"{expected_connector}.yml"
    if decision == "live_connector_preflight_blocked":
        return (
            "Do not configure or use the live connector until every FAIL item is resolved.",
            "Keep LIVE_TRADING_ENABLED=false and GLOBAL_KILL_SWITCH=true.",
            "Remove unexpected live connector config files from scanned Hummingbot mounts.",
            "Rerun Phase 6.3 preflight after fixing the blocked item.",
        )
    if decision == "live_connector_config_pending":
        return (
            "Keep LIVE_TRADING_ENABLED=false and GLOBAL_KILL_SWITCH=true.",
            "Start the Hummingbot CLI container or local Hummingbot CLI.",
            f"In Hummingbot CLI, run `connect {expected_connector}` and paste API keys there only.",
            f"Confirm the host file exists at `{connector_path}`.",
            "Do not paste key values into reports or chat.",
            "Rerun Phase 6.3 preflight and proceed only if the decision becomes ready.",
        )
    return (
        "Keep LIVE_TRADING_ENABLED=false and GLOBAL_KILL_SWITCH=true until live activation.",
        "Do not expand symbols or risk limits beyond BTC-USDT and ETH-USDT.",
        "Proceed to the next phase for final one-batch live activation planning.",
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _decimal_equal(left: object, right: object) -> bool:
    if left is None or right is None:
        return False
    try:
        return Decimal(str(left)) == Decimal(str(right))
    except Exception:
        return str(left) == str(right)


def _json_safe(values: dict[str, object]) -> dict[str, object]:
    return {
        key: decimal_to_str(value) if isinstance(value, Decimal) else value
        for key, value in values.items()
    }
