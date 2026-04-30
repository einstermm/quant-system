"""Detect equivalent research candidates from identical core metrics."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Mapping


EQUIVALENCE_METRIC_KEYS = (
    "total_return",
    "max_drawdown",
    "tail_loss",
    "turnover",
    "trade_count",
    "end_equity",
)


def annotate_metric_equivalence(
    items: list[dict[str, object]],
    *,
    id_key: str,
) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for item in items:
        key = _equivalence_key(_mapping(item.get("metrics")))
        if key:
            groups.setdefault(key, []).append(item)

    for group_key, group in groups.items():
        identifiers = [str(item.get(id_key, "")) for item in group if str(item.get(id_key, ""))]
        for item in group:
            equivalent_count = len(group)
            item["equivalence"] = {
                "status": "equivalent" if equivalent_count > 1 else "unique",
                "group_key": group_key,
                "equivalent_count": equivalent_count,
                "equivalent_ids": identifiers,
                "message": "该结果与其他候选核心指标完全相同。"
                if equivalent_count > 1
                else "该结果暂未发现等价候选。",
            }

    for item in items:
        if "equivalence" not in item:
            item["equivalence"] = {
                "status": "unknown",
                "group_key": "",
                "equivalent_count": 0,
                "equivalent_ids": [],
                "message": "核心指标不足，无法判断等价候选。",
            }
    return items


def _equivalence_key(metrics: Mapping[str, object]) -> str:
    values: list[str] = []
    for key in EQUIVALENCE_METRIC_KEYS:
        value = metrics.get(key)
        normalized = _normalize_metric(value)
        if normalized == "":
            return ""
        values.append(f"{key}={normalized}")
    return "|".join(values)


def _normalize_metric(value: object) -> str:
    if value is None:
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value).strip()
    if not number.is_finite():
        return ""
    return format(number.normalize(), "f")


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}
