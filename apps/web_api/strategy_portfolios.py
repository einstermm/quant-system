"""Persistent multi-strategy portfolio registry for the web dashboard."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from apps.web_api.jobs import STRATEGY_OPTIONS
from apps.web_api.state_db import record_state_document
from apps.web_api.status import REPO_ROOT

STRATEGY_PORTFOLIO_REGISTRY_PATH = Path("reports/web_reviews/strategy_portfolios.json")


def list_strategy_portfolios(*, repo_root: Path = REPO_ROOT) -> dict[str, object]:
    portfolios = _read(repo_root)
    return {
        "registry_path": str(STRATEGY_PORTFOLIO_REGISTRY_PATH),
        "supported_strategies": [
            {"strategy_id": strategy_id, "path": path}
            for strategy_id, path in sorted(STRATEGY_OPTIONS.items())
        ],
        "portfolios": portfolios,
    }


def upsert_strategy_portfolio(
    *,
    portfolio_id: str,
    members: list[Mapping[str, Any]],
    operator_note: str = "",
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    portfolio_id = portfolio_id.strip() or "default_multi_strategy"
    normalized_members = _normalize_members(members)
    now = datetime.now(tz=UTC).isoformat()
    record = {
        "portfolio_id": portfolio_id,
        "updated_at": now,
        "operator_note": operator_note.strip()[:1000],
        "members": normalized_members,
        "total_weight": _format_decimal(sum(Decimal(str(item["weight"])) for item in normalized_members)),
    }

    portfolios = [item for item in _read(repo_root) if str(item.get("portfolio_id", "")) != portfolio_id]
    portfolios.append(record)
    payload = {"portfolios": portfolios}
    path = repo_root / STRATEGY_PORTFOLIO_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    record_state_document(
        key=f"strategy_portfolio:{portfolio_id}",
        source_path=str(STRATEGY_PORTFOLIO_REGISTRY_PATH),
        payload=record,
        repo_root=repo_root,
    )
    return record


def _normalize_members(members: list[Mapping[str, Any]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    total = Decimal("0")
    for item in members:
        strategy_id = str(item.get("strategy_id", "")).strip()
        if strategy_id not in STRATEGY_OPTIONS:
            raise ValueError(f"unsupported portfolio strategy: {strategy_id}")
        if strategy_id in seen:
            raise ValueError(f"duplicate portfolio strategy: {strategy_id}")
        seen.add(strategy_id)
        enabled = bool(item.get("enabled", True))
        weight = _decimal_weight(item.get("weight", "0"))
        if enabled and weight <= 0:
            raise ValueError("enabled strategy weight must be positive")
        if not enabled:
            weight = Decimal("0")
        total += weight
        normalized.append(
            {
                "strategy_id": strategy_id,
                "label": strategy_id,
                "enabled": enabled,
                "weight": _format_decimal(weight),
                "strategy_path": STRATEGY_OPTIONS[strategy_id],
            }
        )
    if not normalized:
        raise ValueError("portfolio must include at least one strategy")
    if total != Decimal("1"):
        raise ValueError("enabled strategy weights must sum to 1")
    return normalized


def _decimal_weight(value: object) -> Decimal:
    try:
        weight = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("strategy weight must be numeric") from exc
    if weight < 0 or weight > 1:
        raise ValueError("strategy weight must be between 0 and 1")
    return weight.quantize(Decimal("0.0001"))


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _read(repo_root: Path) -> list[dict[str, object]]:
    path = repo_root / STRATEGY_PORTFOLIO_REGISTRY_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    portfolios = payload.get("portfolios")
    return [item for item in portfolios if isinstance(item, dict)] if isinstance(portfolios, list) else []
