"""Generate a non-executing live position exit plan."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.adapters.hummingbot.cli_paper_handoff import _write_json, _write_text


@dataclass(frozen=True, slots=True)
class LivePositionExitPlan:
    status: str
    generated_at: datetime
    session_id: str
    strategy_id: str
    account_id: str
    trading_pair: str
    side: str
    quantity: str
    max_exit_notional: str
    exit_reason: str
    checklist: tuple[dict[str, str], ...]
    live_runner_generated: bool
    live_order_submission_armed: bool
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "trading_pair": self.trading_pair,
            "side": self.side,
            "quantity": self.quantity,
            "max_exit_notional": self.max_exit_notional,
            "exit_reason": self.exit_reason,
            "checklist": list(self.checklist),
            "live_runner_generated": self.live_runner_generated,
            "live_order_submission_armed": self.live_order_submission_armed,
            "artifacts": self.artifacts,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Live Position Exit Plan",
            "",
            f"- Status: `{self.status}`",
            f"- Session id: `{self.session_id}`",
            f"- Strategy: `{self.strategy_id}`",
            f"- Account: `{self.account_id}`",
            f"- Pair: `{self.trading_pair}`",
            f"- Side: `{self.side}`",
            f"- Quantity: `{self.quantity}`",
            f"- Max exit notional: `{self.max_exit_notional}`",
            f"- Live runner generated: `{self.live_runner_generated}`",
            f"- Live order submission armed: `{self.live_order_submission_armed}`",
            "",
            "## Checklist",
            "",
        ]
        lines.extend(f"- `{item['status']}` {item['title']}: {item['details']}" for item in self.checklist)
        lines.append("")
        return "\n".join(lines)


def build_live_position_exit_plan(
    *,
    initial_closure: dict[str, Any],
    output_dir: str | Path,
    session_id: str,
    max_exit_notional: Decimal,
    exit_reason: str,
) -> LivePositionExitPlan:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    position = _dict(initial_closure.get("position_lifecycle_plan"))
    quantity = str(position.get("strategy_net_base_quantity", "0"))
    trading_pair = str(position.get("trading_pair", ""))
    checklist = _checklist(initial_closure, quantity=quantity, trading_pair=trading_pair, max_exit_notional=max_exit_notional)
    status = "live_position_exit_plan_blocked" if any(item["status"] == "BLOCK" for item in checklist) else "live_position_exit_plan_ready_for_manual_approval"
    artifacts = {
        "exit_plan_json": str(output_path / "exit_plan.json"),
        "exit_plan_md": str(output_path / "exit_plan.md"),
    }
    plan = LivePositionExitPlan(
        status=status,
        generated_at=datetime.now(tz=UTC),
        session_id=session_id,
        strategy_id=str(initial_closure.get("strategy_id", "")),
        account_id=str(initial_closure.get("account_id", "")),
        trading_pair=trading_pair,
        side="sell",
        quantity=quantity,
        max_exit_notional=str(max_exit_notional),
        exit_reason=exit_reason,
        checklist=tuple(checklist),
        live_runner_generated=False,
        live_order_submission_armed=False,
        artifacts=artifacts,
    )
    _write_json(plan.to_dict(), output_path / "exit_plan.json")
    _write_text(plan.to_markdown(), output_path / "exit_plan.md")
    return plan


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _checklist(
    initial_closure: dict[str, Any],
    *,
    quantity: str,
    trading_pair: str,
    max_exit_notional: Decimal,
) -> list[dict[str, str]]:
    closure = _dict(initial_closure.get("closure_summary"))
    position = _dict(initial_closure.get("position_lifecycle_plan"))
    items = [
        _item("initial_flow_closed", bool(closure.get("initial_flow_closed")), "Initial flow must be closed before exit planning."),
        _item("exit_requires_activation", bool(position.get("exit_requires_activation")), "Exit must require a separate activation."),
        _item("position_quantity", Decimal(str(quantity or "0")) > Decimal("0"), "Position quantity must be positive."),
        _item("trading_pair", bool(trading_pair), "Trading pair must be known."),
        _item("max_exit_notional", max_exit_notional > Decimal("0"), "Max exit notional must be positive."),
    ]
    return items


def _item(item_id: str, ok: bool, details: str) -> dict[str, str]:
    return {"item_id": item_id, "title": item_id.replace("_", " ").title(), "status": "PASS" if ok else "BLOCK", "details": details}


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
