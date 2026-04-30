"""End-to-end operation guide derived from workflow state."""

from __future__ import annotations

from typing import Mapping


def build_operation_guide(workflow: Mapping[str, object]) -> dict[str, object]:
    steps = workflow.get("steps")
    if not isinstance(steps, list):
        steps = []
    active_step_id = str(workflow.get("active_step_id", ""))
    guide_steps = [_guide_step(index + 1, step, active_step_id) for index, step in enumerate(steps) if isinstance(step, dict)]
    return {
        "title": "端到端操作向导",
        "workflow_id": str(workflow.get("workflow_id", "")),
        "active_step_id": active_step_id,
        "current_step": next((step for step in guide_steps if step["is_current"]), None),
        "steps": guide_steps,
        "safety_notes": [
            "Web 只暴露 paper-safe 和审批包生成动作。",
            "Live runner 和 live order submission 保持阻断。",
            "进入下一阶段前先查看当前阶段告警、任务详情和关键产物。",
            "写操作会记录审计日志，并镜像到 SQLite 状态库。",
        ],
    }


def _guide_step(order: int, step: Mapping[str, object], active_step_id: str) -> dict[str, object]:
    actions = step.get("actions")
    action_items = [item for item in actions if isinstance(item, dict)] if isinstance(actions, list) else []
    enabled_actions = [item for item in action_items if bool(item.get("enabled")) and item.get("action_type") == "start_job"]
    next_action = enabled_actions[0] if enabled_actions else None
    runtime_alerts = step.get("runtime_alerts")
    alert_items = [item for item in runtime_alerts if isinstance(item, dict)] if isinstance(runtime_alerts, list) else []
    return {
        "order": order,
        "step_id": str(step.get("step_id", "")),
        "phase": str(step.get("phase", "")),
        "title": str(step.get("title", "")),
        "status": str(step.get("status", "")),
        "decision": str(step.get("decision", "")),
        "is_current": str(step.get("step_id", "")) == active_step_id,
        "runtime_alert_count": len(alert_items),
        "next_action_id": str(next_action.get("action_id", "")) if next_action else "",
        "next_action_label": str(next_action.get("label", "")) if next_action else "查看产物或处理阻断",
        "blocked_actions": [
            {
                "action_id": str(item.get("action_id", "")),
                "label": str(item.get("label", "")),
                "blocked_reason": str(item.get("blocked_reason", "")),
            }
            for item in action_items
            if not bool(item.get("enabled")) and item.get("action_type") == "start_job"
        ],
    }
