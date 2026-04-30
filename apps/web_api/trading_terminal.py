"""Trading terminal aggregation for the web console."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Iterable, Mapping

from apps.web_api.hummingbot_status import build_hummingbot_paper_status
from apps.web_api.live_readiness_summary import build_live_readiness_summary
from apps.web_api.status import CLOSURE_REPORT_PATH
from apps.web_api.status import POST_TRADE_REPORT_PATH
from apps.web_api.status import REPO_ROOT
from apps.web_api.status import build_system_status


ACTIVATION_CHECKLIST_PATH = Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.json")
CONNECTOR_PREFLIGHT_PATH = Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.json")
CANDIDATE_PACKAGE_PATH = Path(
    "reports/live_readiness/"
    "crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/"
    "package.json"
)
RUNNER_PACKAGE_PATH = Path(
    "reports/live_readiness/"
    "crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/"
    "package.json"
)

TERMINAL_SAFE_ACTIONS = (
    {
        "action_id": "generate_live_execution_package",
        "label": "生成 Live 执行申请包",
        "description": "重新生成候选订单和审批包；不生成 runner，不提交订单。",
        "safety_level": "live_package_only",
    },
    {
        "action_id": "generate_live_post_trade_report",
        "label": "生成 Live Post-trade 复盘",
        "description": "读取 live event、Hummingbot DB 和日志生成对账/日报/税务基础导出。",
        "safety_level": "operator_safe",
    },
    {
        "action_id": "generate_live_cooldown_review",
        "label": "生成冷却复盘",
        "description": "复核 runner 停止、配置 disarm 和 open orders 检查。",
        "safety_level": "operator_safe",
    },
    {
        "action_id": "generate_live_initial_closure_report",
        "label": "生成初始闭环报告",
        "description": "基于 post-trade 和 cooldown 复盘冻结初始闭环证据。",
        "safety_level": "operator_safe",
    },
    {
        "action_id": "generate_live_position_exit_plan",
        "label": "生成仓位退出计划",
        "description": "生成真实仓位退出计划和审批清单；不生成 runner，不提交 sell order。",
        "safety_level": "live_plan_only",
    },
)


def build_trading_terminal(
    jobs: Iterable[Mapping[str, object]] = (),
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    """Return the operator-facing trading terminal payload.

    The terminal is deliberately review-only. It aggregates live status,
    candidate orders, risk gates, and reconciliation evidence without exposing
    live runner startup or live order submission.
    """

    system_status = build_system_status(repo_root)
    live_summary = build_live_readiness_summary(repo_root)
    hummingbot = build_hummingbot_paper_status(repo_root=repo_root, jobs=jobs)
    activation = _read_json(repo_root / ACTIVATION_CHECKLIST_PATH)
    connector = _read_json(repo_root / CONNECTOR_PREFLIGHT_PATH)
    candidate_package = _read_json(repo_root / CANDIDATE_PACKAGE_PATH)
    runner_package = _read_json(repo_root / RUNNER_PACKAGE_PATH)
    post_trade = _read_json(repo_root / POST_TRADE_REPORT_PATH)
    closure = _read_json(repo_root / CLOSURE_REPORT_PATH)

    environment = _environment(activation, connector)
    candidate_orders = _candidate_orders(candidate_package)
    risk_summary = _risk_summary(candidate_package, connector, activation, post_trade)
    safety = _safety(environment, candidate_package, runner_package)
    blockers = _blockers(
        system_status=system_status,
        live_summary=live_summary,
        closure=closure,
        post_trade=post_trade,
        safety=safety,
        candidate_package=candidate_package,
        runner_package=runner_package,
    )
    mode = _mode(system_status, live_summary, hummingbot, blockers)

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "mode": mode,
        "safety": safety,
        "account": {
            "account_id": str(_mapping(system_status.get("live")).get("account_id", "")),
            "connector": str(candidate_package.get("connector") or connector.get("expected_connector") or ""),
            "market_type": str(connector.get("market_type", "")),
            "allowed_pairs": _string_list(
                candidate_package.get("allowed_pairs")
                or connector.get("allowed_pairs")
                or _mapping(system_status.get("live")).get("allowed_pairs")
            ),
        },
        "strategy": {
            "strategy_id": str(
                candidate_package.get("strategy_id")
                or closure.get("strategy_id")
                or _mapping(system_status.get("live")).get("strategy_id")
                or ""
            ),
            "signal_summary": _mapping(candidate_package.get("signal_summary")),
        },
        "position": _position(system_status, closure),
        "candidate_orders": {
            "package_path": str(CANDIDATE_PACKAGE_PATH),
            "package_exists": bool(candidate_package),
            "decision": str(candidate_package.get("decision", "missing")),
            "generated_at": str(candidate_package.get("generated_at", "")),
            "execution_runner_generated": bool(candidate_package.get("execution_runner_generated", False)),
            "live_order_submission_armed": bool(candidate_package.get("live_order_submission_armed", False)),
            "orders": candidate_orders,
            "checklist": _checklist(candidate_package),
        },
        "risk": {
            "summary": risk_summary,
            "allowed_pairs": _string_list(
                candidate_package.get("allowed_pairs")
                or _mapping(post_trade.get("risk_checks")).get("allowed_pairs")
                or _mapping(system_status.get("live")).get("allowed_pairs")
            ),
            "checks": _mapping(post_trade.get("risk_checks")),
        },
        "execution": _execution(post_trade, runner_package),
        "hummingbot": hummingbot,
        "blockers": blockers,
        "actions": _terminal_actions(),
        "artifacts": {
            "activation_checklist": str(ACTIVATION_CHECKLIST_PATH),
            "connector_preflight": str(CONNECTOR_PREFLIGHT_PATH),
            "candidate_package": str(CANDIDATE_PACKAGE_PATH),
            "runner_package": str(RUNNER_PACKAGE_PATH),
            "post_trade_report": str(POST_TRADE_REPORT_PATH),
            "initial_closure": str(CLOSURE_REPORT_PATH),
        },
    }


def _environment(*reports: Mapping[str, object]) -> dict[str, object]:
    for report in reports:
        environment = report.get("environment")
        if isinstance(environment, dict) and environment:
            return {
                "live_trading_enabled": bool(environment.get("live_trading_enabled", False)),
                "global_kill_switch": bool(environment.get("global_kill_switch", True)),
                "alert_channel_configured": bool(environment.get("alert_channel_configured", False)),
                "exchange_key_env_detected": bool(environment.get("exchange_key_env_detected", False)),
            }
    return {
        "live_trading_enabled": False,
        "global_kill_switch": True,
        "alert_channel_configured": False,
        "exchange_key_env_detected": False,
    }


def _safety(
    environment: Mapping[str, object],
    candidate_package: Mapping[str, object],
    runner_package: Mapping[str, object],
) -> dict[str, object]:
    live_submission_armed = bool(
        candidate_package.get("live_order_submission_armed")
        or runner_package.get("live_order_submission_armed")
    )
    return {
        "web_mode": "terminal_review_only",
        "live_trading_enabled": bool(environment.get("live_trading_enabled", False)),
        "global_kill_switch": bool(environment.get("global_kill_switch", True)),
        "alert_channel_configured": bool(environment.get("alert_channel_configured", False)),
        "exchange_key_env_detected": bool(environment.get("exchange_key_env_detected", False)),
        "live_runner_exposed": False,
        "live_order_submission_exposed": False,
        "web_can_submit_live_order": False,
        "live_order_submission_armed": live_submission_armed,
        "runner_package_exists": bool(runner_package),
        "runner_disarmed": not live_submission_armed,
    }


def _mode(
    system_status: Mapping[str, object],
    live_summary: Mapping[str, object],
    hummingbot: Mapping[str, object],
    blockers: list[dict[str, object]],
) -> dict[str, object]:
    hbot_status = str(hummingbot.get("status", ""))
    next_decision = str(_mapping(system_status.get("live")).get("next_decision", "unknown"))
    if hbot_status == "observing":
        status = "PAPER_OBSERVING"
        label = "Paper observing"
        reason = "Hummingbot paper session is producing events."
    elif next_decision.startswith("NO_GO") or blockers:
        status = "LIVE_BLOCKED"
        label = "Live blocked"
        reason = str(_mapping(system_status.get("live")).get("next_decision_reason", "")) or "Live blockers are present."
    elif str(live_summary.get("status", "")) == "review_only":
        status = "READY_FOR_MANUAL_REVIEW"
        label = "Ready for manual review"
        reason = "Terminal remains review-only; manual approval is still required."
    else:
        status = "LIVE_REVIEW_ONLY"
        label = "Live review only"
        reason = "Web live runner and order submission remain disabled."
    return {
        "status": status,
        "label": label,
        "reason": reason,
        "next_live_decision": next_decision,
    }


def _position(system_status: Mapping[str, object], closure: Mapping[str, object]) -> dict[str, object]:
    status_position = _mapping(system_status.get("position"))
    lifecycle = _mapping(closure.get("position_lifecycle_plan"))
    return {
        "stance": str(status_position.get("stance") or lifecycle.get("stance") or "unknown"),
        "trading_pair": str(status_position.get("trading_pair") or lifecycle.get("trading_pair") or ""),
        "strategy_net_base_quantity": str(
            status_position.get("strategy_net_base_quantity")
            or lifecycle.get("strategy_net_base_quantity")
            or ""
        ),
        "strategy_gross_base_quantity": str(lifecycle.get("strategy_gross_base_quantity", "")),
        "entry_cost_basis_quote": str(status_position.get("entry_cost_basis_quote") or lifecycle.get("entry_cost_basis_quote") or ""),
        "entry_average_price_quote": str(lifecycle.get("entry_average_price_quote", "")),
        "account_ending_base_balance": str(lifecycle.get("account_ending_base_balance", "")),
        "fee_amount": str(lifecycle.get("fee_amount", "")),
        "fee_asset": str(lifecycle.get("fee_asset", "")),
        "exit_requires_activation": bool(
            status_position.get("exit_requires_activation", lifecycle.get("exit_requires_activation", True))
        ),
        "exit_plan": str(lifecycle.get("exit_plan", "")),
        "hold_until": str(lifecycle.get("hold_until", "")),
    }


def _candidate_orders(candidate_package: Mapping[str, object]) -> list[dict[str, object]]:
    orders = candidate_package.get("candidate_orders")
    if not isinstance(orders, list):
        return []
    risk_summary = _mapping(candidate_package.get("risk_summary"))
    allowed_pairs = set(_string_list(candidate_package.get("allowed_pairs")))
    result: list[dict[str, object]] = []
    for item in orders:
        if not isinstance(item, dict):
            continue
        trading_pair = str(item.get("trading_pair", ""))
        result.append(
            {
                "client_order_id": str(item.get("client_order_id", "")),
                "trading_pair": trading_pair,
                "side": str(item.get("side", "")),
                "order_type": str(item.get("order_type", "")),
                "notional_quote": str(item.get("notional_quote", "")),
                "estimated_price": str(item.get("estimated_price", "")),
                "estimated_quantity": str(item.get("estimated_quantity", "")),
                "signal_timestamp": str(item.get("signal_timestamp", "")),
                "signal_momentum": str(item.get("signal_momentum", "")),
                "risk_checks": {
                    "inside_allowlist": trading_pair in allowed_pairs if trading_pair else False,
                    "max_order_notional": str(risk_summary.get("max_order_notional", "")),
                    "max_batch_notional": str(risk_summary.get("max_batch_notional", "")),
                    "live_order_submission_armed": bool(candidate_package.get("live_order_submission_armed", False)),
                },
            }
        )
    return result


def _risk_summary(*reports: Mapping[str, object]) -> dict[str, object]:
    for report in reports:
        summary = report.get("risk_summary")
        if isinstance(summary, dict) and summary:
            return dict(summary)
    return {}


def _execution(post_trade: Mapping[str, object], runner_package: Mapping[str, object]) -> dict[str, object]:
    fill_summary = _mapping(post_trade.get("fill_summary"))
    order_checks = _mapping(post_trade.get("order_checks"))
    balance_checks = _mapping(post_trade.get("balance_checks"))
    operational_checks = _mapping(post_trade.get("operational_checks"))
    return {
        "status": str(post_trade.get("status", "missing")),
        "generated_at": str(post_trade.get("generated_at", "")),
        "order_checks": order_checks,
        "fill_summary": {
            "gross_quote_notional": str(fill_summary.get("gross_quote_notional", "")),
            "gross_base_quantity": str(fill_summary.get("gross_base_quantity", "")),
            "net_base_quantity": str(fill_summary.get("net_base_quantity", "")),
            "average_price_quote": str(fill_summary.get("average_price_quote", "")),
            "fee_amount": str(fill_summary.get("fee_amount", "")),
            "fee_asset": str(fill_summary.get("fee_asset", "")),
        },
        "balance_checks": balance_checks,
        "operational_checks": operational_checks,
        "runner": {
            "package_exists": bool(runner_package),
            "decision": str(runner_package.get("decision", "missing")),
            "live_order_submission_armed": bool(runner_package.get("live_order_submission_armed", False)),
        },
    }


def _blockers(
    *,
    system_status: Mapping[str, object],
    live_summary: Mapping[str, object],
    closure: Mapping[str, object],
    post_trade: Mapping[str, object],
    safety: Mapping[str, object],
    candidate_package: Mapping[str, object],
    runner_package: Mapping[str, object],
) -> list[dict[str, object]]:
    blockers: list[dict[str, object]] = []
    if not bool(safety.get("live_trading_enabled")):
        blockers.append(_blocker("CRITICAL", "Live trading disabled", "LIVE_TRADING_ENABLED is false.", "safety"))
    if bool(safety.get("global_kill_switch")):
        blockers.append(_blocker("CRITICAL", "Global kill switch enabled", "GLOBAL_KILL_SWITCH is true.", "safety"))
    if not bool(safety.get("live_order_submission_exposed")):
        blockers.append(_blocker("INFO", "Web live submission disabled", "Web cannot submit live orders.", "safety"))
    next_live = _mapping(system_status.get("live"))
    next_decision = str(next_live.get("next_decision", ""))
    if next_decision.startswith("NO_GO"):
        blockers.append(
            _blocker(
                "WARN",
                next_decision,
                str(next_live.get("next_decision_reason", "")) or "Next live decision is blocked.",
                "live_decision",
            )
        )
    for item in live_summary.get("blockers", []) if isinstance(live_summary.get("blockers"), list) else []:
        if isinstance(item, dict):
            blockers.append(
                _blocker(
                    str(item.get("severity", "WARN")),
                    str(item.get("title", "Live readiness blocker")),
                    str(item.get("message", "")),
                    "live_readiness",
                )
            )
    if candidate_package and not bool(candidate_package.get("live_order_submission_armed", False)):
        blockers.append(_blocker("INFO", "Candidate package not armed", "Candidate orders are review-only.", "candidate_package"))
    if runner_package and not bool(runner_package.get("live_order_submission_armed", False)):
        blockers.append(_blocker("INFO", "Runner package disarmed", "The latest runner package is not armed.", "runner_package"))
    for alert in _alerts(closure):
        blockers.append(_blocker(alert["severity"], alert["title"], alert["message"], "initial_closure"))
    for alert in _alerts(post_trade):
        blockers.append(_blocker(alert["severity"], alert["title"], alert["message"], "post_trade"))
    return _sort_blockers(_dedupe_blockers(blockers))


def _terminal_actions() -> list[dict[str, object]]:
    actions = [
        {
            **action,
            "enabled": True,
            "blocked_reason": "",
        }
        for action in TERMINAL_SAFE_ACTIONS
    ]
    actions.append(
        {
            "action_id": "run_live_batch",
            "label": "启动 Live Runner",
            "description": "Web 交易终端第一版不提供实盘启动能力。",
            "safety_level": "live_blocked",
            "enabled": False,
            "blocked_reason": "必须在独立人工流程中审批和启动；Web 不暴露 live runner。",
        }
    )
    return actions


def _checklist(payload: Mapping[str, object]) -> list[dict[str, object]]:
    checklist = payload.get("checklist")
    if not isinstance(checklist, list):
        return []
    result = []
    for item in checklist:
        if isinstance(item, dict):
            result.append(
                {
                    "item_id": str(item.get("item_id", "")),
                    "title": str(item.get("title", "")),
                    "status": str(item.get("status", "")),
                    "details": str(item.get("details", "")),
                }
            )
    return result


def _alerts(payload: Mapping[str, object]) -> list[dict[str, str]]:
    raw_alerts = payload.get("alerts")
    if not isinstance(raw_alerts, list):
        return []
    alerts = []
    for item in raw_alerts:
        if not isinstance(item, dict):
            continue
        alerts.append(
            {
                "severity": str(item.get("severity", "INFO")),
                "title": str(item.get("title", "")),
                "message": str(item.get("message", "")),
            }
        )
    return alerts


def _blocker(severity: str, title: str, message: str, source: str) -> dict[str, object]:
    return {
        "severity": _normalize_severity(severity),
        "title": title,
        "message": message,
        "source": source,
    }


def _dedupe_blockers(blockers: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for item in blockers:
        key = (str(item.get("severity", "")), str(item.get("title", "")), str(item.get("source", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _sort_blockers(blockers: list[dict[str, object]]) -> list[dict[str, object]]:
    priority = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    return sorted(blockers, key=lambda item: priority.get(str(item.get("severity", "INFO")), 3))


def _normalize_severity(value: str) -> str:
    raw = value.upper()
    if raw in {"CRITICAL", "ERROR", "DANGER"}:
        return "CRITICAL"
    if raw in {"WARN", "WARNING"}:
        return "WARN"
    return "INFO"


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
