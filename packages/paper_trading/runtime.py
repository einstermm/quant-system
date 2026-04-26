"""Runtime helpers shared by paper trading CLIs."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from packages.data.simple_yaml import load_simple_yaml
from packages.risk.account_limits import AccountRiskLimits
from packages.risk.kill_switch import KillSwitch


def assert_readiness(path: Path, *, allow_warnings: bool) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    status = payload["status"]
    if status == "paper_ready":
        return
    if status == "paper_ready_with_warnings" and allow_warnings:
        return
    raise SystemExit(f"readiness gate failed: {status}")


def load_risk_limits(path: Path) -> AccountRiskLimits:
    payload = load_simple_yaml(path)
    return AccountRiskLimits(
        max_order_notional=Decimal(str(payload["max_order_notional"])),
        max_symbol_notional=Decimal(str(payload["max_symbol_notional"])),
        max_gross_notional=Decimal(str(payload["max_gross_notional"])),
        max_daily_loss=Decimal(str(payload["max_daily_loss"])),
        max_drawdown_pct=Decimal(str(payload["max_drawdown_pct"])),
    )


def load_kill_switch(path: Path | None) -> KillSwitch:
    if path is None:
        return KillSwitch()
    if not path.exists():
        raise SystemExit(f"kill switch file does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return KillSwitch(
        active=bool(payload.get("active", False)),
        reason=str(payload.get("reason", "manual kill switch")),
    )
