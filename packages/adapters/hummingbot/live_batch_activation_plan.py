"""Phase 6.4 first live batch activation plan."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from packages.backtesting.result import decimal_to_str
from packages.data.simple_yaml import load_simple_yaml


@dataclass(frozen=True, slots=True)
class LiveBatchPlanCheckItem:
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
class LiveBatchActivationPlan:
    decision: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    batch_id: str
    connector: str
    market_type: str
    allowed_pairs: tuple[str, ...]
    batch_scope: dict[str, object]
    risk_controls: dict[str, object]
    environment: dict[str, object]
    checklist: tuple[LiveBatchPlanCheckItem, ...]
    activation_sequence: tuple[str, ...]
    rollback_sequence: tuple[str, ...]
    post_batch_sequence: tuple[str, ...]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "batch_id": self.batch_id,
            "connector": self.connector,
            "market_type": self.market_type,
            "allowed_pairs": list(self.allowed_pairs),
            "batch_scope": self.batch_scope,
            "risk_controls": self.risk_controls,
            "environment": self.environment,
            "checklist": [item.to_dict() for item in self.checklist],
            "activation_sequence": list(self.activation_sequence),
            "rollback_sequence": list(self.rollback_sequence),
            "post_batch_sequence": list(self.post_batch_sequence),
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 6.4 First Live Batch Activation Plan",
            "",
            f"- Generated at: `{self.generated_at.isoformat()}`",
            f"- Decision: `{self.decision}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Batch id: `{self.batch_id}`",
            f"- Connector: `{self.connector}`",
            f"- Market type: `{self.market_type}`",
            f"- Allowed pairs: `{', '.join(self.allowed_pairs)}`",
            "",
            "## Batch Scope",
            "",
        ]
        lines.extend(f"- {key}: `{value}`" for key, value in self.batch_scope.items())
        lines.extend(["", "## Risk Controls", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.risk_controls.items())
        lines.extend(["", "## Environment", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.environment.items())
        lines.extend(["", "## Checklist", ""])
        lines.extend(
            f"- `{item.status}` {item.title}: {item.details}"
            + (f" Evidence: `{item.evidence}`" if item.evidence else "")
            for item in self.checklist
        )
        lines.extend(["", "## Activation Sequence", ""])
        lines.extend(
            f"{index}. {step}"
            for index, step in enumerate(self.activation_sequence, start=1)
        )
        lines.extend(["", "## Rollback Sequence", ""])
        lines.extend(
            f"{index}. {step}"
            for index, step in enumerate(self.rollback_sequence, start=1)
        )
        lines.extend(["", "## Post Batch Sequence", ""])
        lines.extend(
            f"{index}. {step}"
            for index, step in enumerate(self.post_batch_sequence, start=1)
        )
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- {key}: `{value}`" for key, value in self.artifacts.items())
        lines.append("")
        return "\n".join(lines)


def build_live_batch_activation_plan(
    *,
    live_connector_preflight: dict[str, Any],
    credential_allowlist: dict[str, Any],
    operator_signoff: dict[str, Any],
    live_risk_config: dict[str, Any],
    environment: dict[str, object],
    session_id: str,
    strategy_id: str,
    batch_id: str,
    allowed_pairs: Iterable[str],
    max_batch_orders: int,
    max_batch_notional: Decimal,
    final_operator_go: bool = False,
    artifacts: dict[str, str] | None = None,
) -> LiveBatchActivationPlan:
    pair_tuple = tuple(allowed_pairs)
    connector = str(live_connector_preflight.get("expected_connector", ""))
    market_type = str(live_connector_preflight.get("market_type", ""))
    risk_controls = _risk_controls(
        live_risk_config=live_risk_config,
        max_batch_orders=max_batch_orders,
        max_batch_notional=max_batch_notional,
    )
    batch_scope = _batch_scope(
        batch_id=batch_id,
        connector=connector,
        market_type=market_type,
        allowed_pairs=pair_tuple,
        risk_controls=risk_controls,
    )
    checklist = _checklist(
        live_connector_preflight=live_connector_preflight,
        credential_allowlist=credential_allowlist,
        operator_signoff=operator_signoff,
        risk_controls=risk_controls,
        environment=environment,
        allowed_pairs=pair_tuple,
        max_batch_orders=max_batch_orders,
        final_operator_go=final_operator_go,
    )
    decision = _decision(checklist)
    return LiveBatchActivationPlan(
        decision=decision,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=strategy_id,
        batch_id=batch_id,
        connector=connector,
        market_type=market_type,
        allowed_pairs=pair_tuple,
        batch_scope=batch_scope,
        risk_controls=risk_controls,
        environment=environment,
        checklist=tuple(checklist),
        activation_sequence=_activation_sequence(
            decision,
            max_batch_orders=max_batch_orders,
            max_batch_notional=max_batch_notional,
        ),
        rollback_sequence=_rollback_sequence(),
        post_batch_sequence=_post_batch_sequence(),
        artifacts=artifacts or {},
    )


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_risk_config(path: str | Path) -> dict[str, Any]:
    return load_simple_yaml(path)


def write_live_batch_activation_plan_json(
    report: LiveBatchActivationPlan,
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_live_batch_activation_plan_markdown(
    report: LiveBatchActivationPlan,
    path: str | Path,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return output_path


def _risk_controls(
    *,
    live_risk_config: dict[str, Any],
    max_batch_orders: int,
    max_batch_notional: Decimal,
) -> dict[str, object]:
    max_order = _decimal(live_risk_config.get("max_order_notional"))
    max_symbol = _decimal(live_risk_config.get("max_symbol_notional"))
    max_gross = _decimal(live_risk_config.get("max_gross_notional"))
    max_daily_loss = _decimal(live_risk_config.get("max_daily_loss"))
    max_drawdown_pct = _decimal(live_risk_config.get("max_drawdown_pct"))
    return {
        "max_batch_orders": max_batch_orders,
        "max_batch_notional": decimal_to_str(max_batch_notional),
        "max_order_notional": decimal_to_str(max_order),
        "max_symbol_notional": decimal_to_str(max_symbol),
        "max_gross_notional": decimal_to_str(max_gross),
        "max_daily_loss": decimal_to_str(max_daily_loss),
        "max_drawdown_pct": decimal_to_str(max_drawdown_pct),
        "one_batch_only": True,
        "auto_expand_pairs": False,
        "auto_expand_limits": False,
        "spot_only_no_margin": True,
        "sell_only_existing_spot_balance": True,
    }


def _batch_scope(
    *,
    batch_id: str,
    connector: str,
    market_type: str,
    allowed_pairs: tuple[str, ...],
    risk_controls: dict[str, object],
) -> dict[str, object]:
    return {
        "batch_id": batch_id,
        "mode": "single_supervised_live_batch",
        "connector": connector,
        "market_type": market_type,
        "allowed_pairs": list(allowed_pairs),
        "max_orders": risk_controls["max_batch_orders"],
        "max_total_notional": risk_controls["max_batch_notional"],
        "live_order_submission_armed": False,
        "requires_final_operator_go": True,
    }


def _checklist(
    *,
    live_connector_preflight: dict[str, Any],
    credential_allowlist: dict[str, Any],
    operator_signoff: dict[str, Any],
    risk_controls: dict[str, object],
    environment: dict[str, object],
    allowed_pairs: tuple[str, ...],
    max_batch_orders: int,
    final_operator_go: bool,
) -> list[LiveBatchPlanCheckItem]:
    preflight_pairs = tuple(
        str(pair)
        for pair in _list(live_connector_preflight.get("allowed_pairs"))
    )
    credential_pairs = tuple(
        str(pair)
        for pair in _dict(credential_allowlist.get("first_live_allowlist")).get("trading_pairs", [])
    )
    operator_pairs = tuple(
        str(pair)
        for pair in _list(operator_signoff.get("first_live_allowlist"))
    )
    connector_status = _dict(live_connector_preflight.get("connector_status"))
    return [
        _item(
            "phase_6_3_preflight",
            "Phase 6.3 live connector preflight ready",
            "PASS"
            if live_connector_preflight.get("decision") == "live_connector_preflight_ready"
            else "FAIL",
            f"Phase 6.3 decision is {live_connector_preflight.get('decision', 'unknown')}.",
            str(connector_status.get("expected_host_config_path", "")),
        ),
        _item(
            "symbol_allowlist",
            "First live allowlist remains exact",
            "PASS"
            if preflight_pairs == allowed_pairs
            and credential_pairs == allowed_pairs
            and operator_pairs == allowed_pairs
            else "FAIL",
            (
                f"preflight={preflight_pairs or 'unknown'}; "
                f"credential={credential_pairs or 'unknown'}; "
                f"operator={operator_pairs or 'unknown'}."
            ),
        ),
        _item(
            "batch_order_count",
            "Batch order count is capped",
            "PASS" if 0 < max_batch_orders <= len(allowed_pairs) else "FAIL",
            f"max_batch_orders={max_batch_orders}; allowed_pairs={len(allowed_pairs)}.",
        ),
        _item(
            "batch_notional_cap",
            "Batch notional is inside gross risk limit",
            "PASS"
            if _decimal(risk_controls["max_batch_notional"])
            <= _decimal(risk_controls["max_gross_notional"])
            else "FAIL",
            (
                f"max_batch_notional={risk_controls['max_batch_notional']}; "
                f"max_gross_notional={risk_controls['max_gross_notional']}."
            ),
        ),
        _item(
            "single_order_cap",
            "Single order cap remains approved",
            "PASS" if _decimal(risk_controls["max_order_notional"]) <= Decimal("250") else "FAIL",
            f"max_order_notional={risk_controls['max_order_notional']}; approved=250.",
        ),
        _item(
            "live_disabled",
            "Live trading remains disabled before final go",
            "PASS" if not bool(environment.get("live_trading_enabled")) else "FAIL",
            "LIVE_TRADING_ENABLED must stay false while this is only a plan.",
        ),
        _item(
            "kill_switch_enabled",
            "Global kill switch remains enabled before final go",
            "PASS" if bool(environment.get("global_kill_switch")) else "FAIL",
            "GLOBAL_KILL_SWITCH must stay true until the explicit activation step.",
        ),
        _item(
            "alert_channel",
            "External alert channel remains configured",
            "PASS" if bool(environment.get("alert_channel_configured")) else "FAIL",
            "External alerts are required for any live batch.",
        ),
        _item(
            "exchange_keys_not_in_quant_env",
            "Exchange keys are not stored in quant-system env",
            "PASS" if not bool(environment.get("exchange_key_env_detected")) else "FAIL",
            "Real exchange credentials must stay in Hummingbot connector config.",
        ),
        _item(
            "operator_final_go",
            "Final operator go/no-go",
            "PASS" if final_operator_go else "MANUAL_REQUIRED",
            "Final operator go has been recorded."
            if final_operator_go
            else "A separate final operator go is required before any real order is submitted.",
        ),
    ]


def _item(
    item_id: str,
    title: str,
    status: str,
    details: str,
    evidence: str = "",
) -> LiveBatchPlanCheckItem:
    return LiveBatchPlanCheckItem(
        item_id=item_id,
        title=title,
        status=status,
        details=details,
        evidence=evidence,
    )


def _decision(checklist: list[LiveBatchPlanCheckItem]) -> str:
    if any(item.status == "FAIL" for item in checklist):
        return "live_batch_activation_plan_blocked"
    if any(item.status == "MANUAL_REQUIRED" for item in checklist):
        return "live_batch_activation_plan_ready_pending_operator_go"
    return "live_batch_activation_plan_approved"


def _activation_sequence(
    decision: str,
    *,
    max_batch_orders: int,
    max_batch_notional: Decimal,
) -> tuple[str, ...]:
    if decision == "live_batch_activation_plan_blocked":
        return (
            "Do not enable live trading.",
            "Fix every FAIL checklist item, then regenerate Phase 6.4.",
        )
    return (
        "Rerun Phase 6.3 immediately before the live batch.",
        "Send and verify one external alert test.",
        "Confirm Binance spot account balances and no unexpected open orders.",
        "Generate the final live batch from the latest BTC/ETH-only signal.",
        (
            f"Cap the batch to {max_batch_orders} order(s) and "
            f"{decimal_to_str(max_batch_notional)} USDT total notional."
        ),
        "Only after final operator go, arm the one-batch live runner.",
        "Submit one supervised batch only, then immediately disarm live trading.",
    )


def _rollback_sequence() -> tuple[str, ...]:
    return (
        "Stop the Hummingbot container or script immediately.",
        "Set GLOBAL_KILL_SWITCH=true and LIVE_TRADING_ENABLED=false.",
        "Cancel any open orders in Hummingbot and confirm in the Binance spot UI.",
        "Do not restart live trading before reconciliation is complete.",
    )


def _post_batch_sequence() -> tuple[str, ...]:
    return (
        "Export Hummingbot events and exchange fills.",
        "Run daily report, reconciliation, and tax/trade export.",
        "Compare Hummingbot fills against Binance fills and balances.",
        "Document PnL, fees, slippage, alerts, and any manual intervention.",
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))
