"""Business workflow aggregation for the web UI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from apps.web_api.backtest_candidates import BACKTEST_CANDIDATE_PATH
from apps.web_api.jobs import latest_candidate_capacity_stress_evidence
from apps.web_api.jobs import latest_candidate_walk_forward_evidence
from apps.web_api.jobs import latest_hummingbot_runtime_preflight
from apps.web_api.jobs import latest_hummingbot_export_acceptance
from apps.web_api.jobs import latest_hummingbot_sandbox_prepare
from apps.web_api.jobs import latest_hummingbot_cli_direct_paper_handoff
from apps.web_api.jobs import latest_hummingbot_cli_direct_paper_install
from apps.web_api.jobs import latest_hummingbot_paper_event_collection
from apps.web_api.jobs import latest_paper_observation_review
from apps.web_api.jobs import latest_paper_smoke_evidence
from apps.web_api.jobs import latest_passed_paper_readiness
from apps.web_api.jobs import job_parameter_definitions
from apps.web_api.readiness_disposition_state import disposition_resolution
from apps.web_api.readiness_disposition_state import read_recorded_disposition
from apps.web_api.status import (
    CLOSURE_REPORT_PATH,
    COOLDOWN_REPORT_PATH,
    POST_TRADE_REPORT_PATH,
    REPO_ROOT,
)


JOB_ALERT_DEFINITIONS: dict[str, tuple[str, str]] = {
    "failed": ("error", "任务失败"),
    "timed_out": ("error", "任务超时"),
    "interrupted": ("error", "任务中断"),
    "canceled": ("warning", "任务已取消"),
}


@dataclass(frozen=True, slots=True)
class WorkflowArtifact:
    label: str
    path: Path
    kind: str = "report"

    def to_dict(self, repo_root: Path) -> dict[str, object]:
        absolute = repo_root / self.path
        return {
            "label": self.label,
            "path": str(self.path),
            "kind": self.kind,
            "exists": absolute.exists(),
        }


@dataclass(frozen=True, slots=True)
class WorkflowAction:
    action_id: str
    label: str
    action_type: str
    enabled: bool
    safety_level: str
    description: str
    blocked_reason: str = ""

    def to_dict(self, latest_job: Mapping[str, object] | None = None) -> dict[str, object]:
        runtime_alert = _runtime_alert_for_job(self, latest_job)
        parameters = (
            [parameter.to_dict() for parameter in job_parameter_definitions(self.action_id)]
            if self.action_type == "start_job"
            else []
        )
        return {
            "action_id": self.action_id,
            "label": self.label,
            "action_type": self.action_type,
            "enabled": self.enabled,
            "safety_level": self.safety_level,
            "description": self.description,
            "blocked_reason": self.blocked_reason,
            "parameters": parameters,
            "latest_job": _compact_job(latest_job) if latest_job else None,
            "runtime_alert": runtime_alert,
            "output_dir_template": "reports/web_jobs/<generated-job-id>/"
            if self.action_type == "start_job"
            else "",
        }


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    phase: str
    title: str
    business_goal: str
    status: str
    decision: str
    owner: str
    inputs: tuple[WorkflowArtifact, ...]
    outputs: tuple[WorkflowArtifact, ...]
    actions: tuple[WorkflowAction, ...]
    notes: tuple[str, ...] = ()

    def to_dict(
        self,
        repo_root: Path,
        latest_jobs_by_action: Mapping[str, Mapping[str, object]],
    ) -> dict[str, object]:
        action_payloads = [
            action.to_dict(latest_job=latest_jobs_by_action.get(action.action_id))
            for action in self.actions
        ]
        runtime_alerts = [
            alert
            for action_payload in action_payloads
            if (alert := action_payload.get("runtime_alert")) is not None
        ]
        runtime_status = _runtime_status(runtime_alerts)
        return {
            "step_id": self.step_id,
            "phase": self.phase,
            "title": self.title,
            "business_goal": self.business_goal,
            "status": "attention_required" if runtime_alerts else self.status,
            "base_status": self.status,
            "runtime_status": runtime_status,
            "decision": self.decision,
            "owner": self.owner,
            "inputs": [artifact.to_dict(repo_root) for artifact in self.inputs],
            "outputs": [artifact.to_dict(repo_root) for artifact in self.outputs],
            "actions": action_payloads,
            "runtime_alerts": runtime_alerts,
            "notes": list(self.notes),
        }


def build_v0_workflow(
    repo_root: Path = REPO_ROOT,
    jobs: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Return the end-to-end v0 business workflow for the web console."""

    latest_jobs_by_action = _latest_jobs_by_action(jobs)
    closure = _read_json(repo_root / CLOSURE_REPORT_PATH)
    cooldown = _read_json(repo_root / COOLDOWN_REPORT_PATH)
    post_trade = _read_json(repo_root / POST_TRADE_REPORT_PATH)
    next_live_decision = _dict(closure.get("next_live_decision"))
    closure_summary = _dict(closure.get("closure_summary"))

    steps = (
        _data_step(repo_root),
        _research_step(repo_root),
        _paper_readiness_step(repo_root),
        _paper_observation_step(repo_root),
        _hummingbot_paper_step(repo_root),
        _live_readiness_step(repo_root),
        _first_live_batch_step(repo_root),
        _post_trade_step(post_trade),
        _cooldown_step(cooldown),
        _closure_step(closure),
    )
    active_step_id = _active_step_id(
        next_live_decision=str(next_live_decision.get("decision", "")),
        initial_flow_closed=bool(closure_summary.get("initial_flow_closed", False)),
    )
    return {
        "workflow_id": "v0_initial_flow",
        "title": "V0 初始闭环业务流程",
        "mode": "workflow_console",
        "active_step_id": active_step_id,
        "summary": {
            "strategy_id": str(closure.get("strategy_id", "crypto_relative_strength_v1")),
            "account_id": str(closure.get("account_id", "")),
            "current_status": str(closure.get("status", "unknown")),
            "next_live_decision": str(next_live_decision.get("decision", "unknown")),
            "next_live_reason": str(next_live_decision.get("reason", "")),
            "live_actions_exposed": False,
        },
        "steps": [step.to_dict(repo_root, latest_jobs_by_action) for step in steps],
    }


def _data_step(repo_root: Path) -> WorkflowStep:
    quality_report = Path("data/reports/binance_spot_largecap_4h_2023_2025_sqlite_load_quality.json")
    db = Path("data/warehouse/quant_system.sqlite")
    return WorkflowStep(
        step_id="data_layer",
        phase="Phase 2",
        title="市场数据准备",
        business_goal="准备可复现的 BTC/ETH/大币种 4h K 线数据，并完成质量检查。",
        status="completed" if (repo_root / db).exists() else "attention_required",
        decision="data_ready" if (repo_root / db).exists() else "data_missing",
        owner="research",
        inputs=(WorkflowArtifact("Binance public candles", Path("data/raw/binance_spot_largecap_4h_2023_2025.csv"), "data"),),
        outputs=(WorkflowArtifact("SQLite warehouse", db, "database"), WorkflowArtifact("Quality report", quality_report),),
        actions=(
            WorkflowAction(
                "view_data_quality",
                "查看数据质量",
                "view_artifact",
                True,
                "read_only",
                "查看导入后的 K 线质量报告。",
            ),
            WorkflowAction(
                "refresh_market_data",
                "刷新公开行情",
                "start_job",
                True,
                "paper_safe",
                "调用 Binance public data refresh，把策略需要的近期 K 线写入 SQLite；不涉及交易密钥。",
            ),
            WorkflowAction(
                "query_strategy_data_quality",
                "检查策略数据质量",
                "start_job",
                True,
                "read_only",
                "查询策略所需 K 线覆盖、缺口和质量问题，输出 Web job JSON。",
            ),
        ),
    )


def _research_step(repo_root: Path) -> WorkflowStep:
    wf = Path("reports/backtests/crypto_relative_strength_v1_phase_3_8_execution_constraints_walk_forward.json")
    stress = Path("reports/backtests/crypto_relative_strength_v1_phase_3_8_capacity_stress_1m.json")
    candidate = _read_json(repo_root / BACKTEST_CANDIDATE_PATH)
    candidate_job_id = str(candidate.get("job_id", ""))
    candidate_ready = bool(candidate_job_id)
    complete = candidate_ready or ((repo_root / wf).exists() and (repo_root / stress).exists())
    outputs = [WorkflowArtifact("Walk-forward report", wf), WorkflowArtifact("Capacity stress report", stress)]
    if candidate_ready:
        outputs.append(WorkflowArtifact("Confirmed backtest candidate", BACKTEST_CANDIDATE_PATH))
    notes = []
    if candidate_ready:
        notes.append(f"Confirmed candidate job: {candidate_job_id}")
    disposition = disposition_resolution(read_recorded_disposition(repo_root), candidate)
    if disposition.get("resolution_status") == "requires_new_candidate":
        notes.append(str(disposition.get("message", "")))
    elif disposition.get("resolution_status") == "superseded":
        notes.append(str(disposition.get("message", "")))
    return WorkflowStep(
        step_id="research_backtest",
        phase="Phase 3",
        title="研究与稳健性验证",
        business_goal="用回测、参数扫描、train/test 和 walk-forward 选择候选策略。",
        status="completed" if complete else "attention_required",
        decision="backtest_candidate_confirmed"
        if candidate_ready
        else ("research_candidate_ready" if complete else "research_reports_missing"),
        owner="research",
        inputs=(WorkflowArtifact("Strategy config", Path("strategies/crypto_relative_strength_v1/config.yml"), "config"),),
        outputs=tuple(outputs),
        actions=(
            WorkflowAction(
                "view_backtest",
                "查看回测结果",
                "view_artifact",
                True,
                "read_only",
                "查看 walk-forward、容量和风险覆盖结果。",
            ),
            WorkflowAction(
                "run_backtest",
                "重新运行回测",
                "start_job",
                True,
                "paper_safe",
                "调用 packages.backtesting.run_backtest，输出到 reports/web_jobs。",
            ),
            WorkflowAction(
                "run_parameter_scan",
                "运行参数扫描",
                "start_job",
                True,
                "paper_safe",
                "批量扫描策略参数并生成候选推荐列表。",
            ),
            WorkflowAction(
                "run_candidate_walk_forward",
                "生成候选 Walk-forward",
                "start_job",
                candidate_ready,
                "paper_safe",
                "基于已确认候选参数生成候选专属 walk-forward 证据。",
                "" if candidate_ready else "需要先确认候选回测。",
            ),
            WorkflowAction(
                "run_candidate_capacity_stress",
                "生成候选 Capacity Stress",
                "start_job",
                candidate_ready,
                "paper_safe",
                "基于已确认候选参数运行高资金容量压力回测。",
                "" if candidate_ready else "需要先确认候选回测。",
            ),
        ),
        notes=tuple(note for note in notes if note),
    )


def _paper_readiness_step(repo_root: Path) -> WorkflowStep:
    readiness = Path("reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json")
    payload = _read_json(repo_root / readiness)
    status = str(payload.get("status", "unknown"))
    candidate = _read_json(repo_root / BACKTEST_CANDIDATE_PATH)
    candidate_job_id = str(candidate.get("job_id", ""))
    candidate_strategy_id = str(candidate.get("strategy_id", ""))
    evidence_inputs = [WorkflowArtifact("Confirmed backtest candidate", BACKTEST_CANDIDATE_PATH)]
    candidate_walk_forward = latest_candidate_walk_forward_evidence(repo_root, candidate) if candidate_job_id else {}
    candidate_capacity = latest_candidate_capacity_stress_evidence(repo_root, candidate) if candidate_job_id else {}
    if candidate_walk_forward:
        evidence_inputs.append(WorkflowArtifact("Candidate walk-forward report", Path(str(candidate_walk_forward["walk_forward_json"]))))
    if candidate_capacity:
        evidence_inputs.append(WorkflowArtifact("Candidate capacity stress report", Path(str(candidate_capacity["capacity_stress_json"]))))
    notes = []
    if candidate_job_id:
        notes.append(f"Readiness candidate input: {candidate_job_id}")
    if candidate_job_id:
        if candidate_walk_forward:
            notes.append(f"Candidate walk-forward evidence: {candidate_walk_forward.get('job_id', '')}")
        else:
            notes.append("Candidate walk-forward evidence missing.")
        if candidate_capacity:
            notes.append(f"Candidate capacity stress evidence: {candidate_capacity.get('job_id', '')}")
        else:
            notes.append("Candidate capacity stress evidence missing.")
    disposition = disposition_resolution(read_recorded_disposition(repo_root), candidate)
    if disposition.get("resolution_status") in {"requires_new_candidate", "superseded"}:
        notes.append(str(disposition.get("message", "")))
    disposition_blocks_rerun = disposition.get("resolution_status") == "requires_new_candidate"
    evidence_blocked_reason = _readiness_evidence_blocked_reason(
        candidate_job_id=candidate_job_id,
        has_candidate_walk_forward=bool(candidate_walk_forward),
        has_candidate_capacity=bool(candidate_capacity),
    )
    return WorkflowStep(
        step_id="paper_readiness",
        phase="Phase 3.9",
        title="Paper 准入门禁",
        business_goal="确认候选策略满足进入 paper 的历史表现、容量和风险阈值。",
        status="completed" if status in {"paper_ready", "paper_ready_with_warnings"} else "attention_required",
        decision=status,
        owner="risk",
        inputs=tuple(evidence_inputs),
        outputs=(WorkflowArtifact("Paper readiness", readiness), WorkflowArtifact("Risk-off runbook", Path("reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_risk_off_runbook.md")),),
        actions=(
            WorkflowAction(
                "view_paper_readiness",
                "查看准入报告",
                "view_artifact",
                True,
                "read_only",
                "查看 paper readiness 和 warnings。",
            ),
            WorkflowAction(
                "generate_paper_readiness",
                "生成 Paper 准入",
                "start_job",
                bool(candidate_job_id) and not disposition_blocks_rerun and not evidence_blocked_reason,
                "paper_safe",
                "基于已确认候选回测和候选专属证据重新生成 paper readiness JSON/Markdown/runbook。",
                str(disposition.get("message", ""))
                if disposition_blocks_rerun
                else evidence_blocked_reason,
            ),
        ),
        notes=tuple(notes),
    )


def _paper_observation_step(repo_root: Path) -> WorkflowStep:
    review = Path("reports/paper_trading/crypto_relative_strength_v1_phase_4_3_observation_review.json")
    payload = _read_json(repo_root / review)
    decision = str(payload.get("decision", "unknown"))
    passed_readiness = latest_passed_paper_readiness(repo_root)
    paper_smoke = latest_paper_smoke_evidence(repo_root)
    readiness_input = (
        Path(str(passed_readiness["readiness_json"]))
        if passed_readiness
        else Path("reports/paper_readiness/crypto_relative_strength_v1_phase_3_9_readiness.json")
    )
    return WorkflowStep(
        step_id="local_paper_observation",
        phase="Phase 4",
        title="本地 Paper 观察",
        business_goal="连续跑本地 paper cycle，验证数据刷新、风控审批、ledger 和权益重建。",
        status="completed" if decision.startswith("sandbox_ready") else "attention_required",
        decision=decision,
        owner="operator",
        inputs=(WorkflowArtifact("Paper readiness", readiness_input),),
        outputs=(WorkflowArtifact("24h paper observation review", review), WorkflowArtifact("Paper ledger", Path("reports/paper_trading/crypto_relative_strength_v1_phase_4_2_24h_ledger.jsonl"), "ledger"),),
        actions=(
            WorkflowAction(
                "view_paper_observation",
                "查看观察复盘",
                "view_artifact",
                True,
                "read_only",
                "查看 24 小时 paper observation 复盘。",
            ),
            WorkflowAction(
                "run_paper_smoke",
                "运行 Paper Smoke",
                "start_job",
                bool(passed_readiness),
                "paper_safe",
                "使用最新通过的候选 Paper 准入运行 1-cycle 本地 paper observation。",
                "" if passed_readiness else "需要先生成通过的 Paper 准入报告。",
            ),
            WorkflowAction(
                "generate_paper_observation_review",
                "生成 Paper 观察复盘",
                "start_job",
                bool(paper_smoke),
                "paper_safe",
                "使用最新成功的 Web Paper Smoke 生成观察复盘，作为 Hummingbot sandbox 准备输入。",
                "" if paper_smoke else "需要先成功运行 Paper Smoke。",
            ),
        ),
        notes=(
            (f"Paper smoke readiness input: {passed_readiness.get('job_id', '')}" if passed_readiness else "No passed Web paper readiness report."),
            (f"Latest Web paper smoke: {paper_smoke.get('job_id', '')}" if paper_smoke else "No successful Web paper smoke evidence."),
        ),
    )


def _hummingbot_paper_step(repo_root: Path) -> WorkflowStep:
    review = Path("reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.json")
    payload = _read_json(repo_root / review)
    decision = str(payload.get("decision", "unknown"))
    paper_review = latest_paper_observation_review(repo_root)
    sandbox_prepare = latest_hummingbot_sandbox_prepare(repo_root)
    runtime_preflight = latest_hummingbot_runtime_preflight(repo_root)
    handoff = latest_hummingbot_cli_direct_paper_handoff(repo_root)
    install = latest_hummingbot_cli_direct_paper_install(repo_root)
    event_collection = latest_hummingbot_paper_event_collection(repo_root)
    export_acceptance = latest_hummingbot_export_acceptance(repo_root)
    has_handoff_inputs = bool(sandbox_prepare and runtime_preflight)
    has_acceptance_inputs = bool(sandbox_prepare.get("sandbox_prepare_json"))
    return WorkflowStep(
        step_id="hummingbot_paper",
        phase="Phase 5",
        title="Hummingbot Paper / Sandbox",
        business_goal="把 paper 订单交接给 Hummingbot CLI，采集事件并完成订单/成交/余额对账。",
        status="completed" if decision.startswith("hummingbot_observation_window_ready") else "attention_required",
        decision=decision,
        owner="operator",
        inputs=(WorkflowArtifact("Sandbox manifest", Path("reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_sandbox_manifest.json")),),
        outputs=(WorkflowArtifact("Hummingbot observation review", review),),
        actions=(
            WorkflowAction(
                "view_hummingbot_paper",
                "查看 Hummingbot 复盘",
                "view_artifact",
                True,
                "read_only",
                "查看 Hummingbot paper observation 和 carry-forward warnings。",
            ),
            WorkflowAction(
                "run_hummingbot_sandbox_prepare",
                "生成 Hummingbot Sandbox 准备",
                "start_job",
                bool(paper_review),
                "paper_safe",
                "使用 Web Paper 观察复盘生成 Hummingbot paper/sandbox manifest 和准备报告；不会启动 Hummingbot。",
                "" if paper_review else "需要先生成 Paper 观察复盘。",
            ),
            WorkflowAction(
                "run_hummingbot_runtime_preflight",
                "运行 Hummingbot Runtime Preflight",
                "start_job",
                True,
                "paper_safe",
                "扫描 Hummingbot 挂载目录，确认 paper connector 和 live connector 风险；不会启动 Hummingbot。",
            ),
            WorkflowAction(
                "run_hummingbot_cli_direct_paper_handoff",
                "生成 CLI Direct Paper Handoff",
                "start_job",
                has_handoff_inputs,
                "paper_safe",
                "生成 Hummingbot CLI paper-mode 脚本和配置；不会启动 Hummingbot。",
                "" if has_handoff_inputs else "需要先生成 Hummingbot Sandbox 准备并运行 Runtime Preflight。",
            ),
            WorkflowAction(
                "install_hummingbot_cli_direct_paper_files",
                "安装 CLI Direct Paper 文件",
                "start_job",
                bool(handoff),
                "paper_safe",
                "把最新 Hummingbot CLI paper 脚本和 script config 复制到 Hummingbot root；不会启动 Hummingbot。",
                "" if handoff else "需要先生成 CLI Direct Paper Handoff。",
            ),
            WorkflowAction(
                "run_hummingbot_paper_session_control",
                "控制 Paper Session",
                "start_job",
                bool(install),
                "paper_safe",
                "生成 Hummingbot paper 启停命令，并记录人工已启动/已停止状态；Web 不直接启动进程。",
                "" if install else "需要先安装 CLI Direct Paper 文件。",
            ),
            WorkflowAction(
                "collect_hummingbot_paper_events",
                "采集 Paper Events",
                "start_job",
                (repo_root / "reports/web_reviews/hummingbot_paper_session_state.json").exists(),
                "paper_safe",
                "从 Hummingbot paper event JSONL 采集事件到 Web job 目录，供 Export Acceptance 使用。",
                ""
                if (repo_root / "reports/web_reviews/hummingbot_paper_session_state.json").exists()
                else "需要先记录 Paper Session 已启动或已停止。",
            ),
            WorkflowAction(
                "run_hummingbot_export_acceptance",
                "运行 Hummingbot Export Acceptance",
                "start_job",
                has_acceptance_inputs,
                "paper_safe",
                "验收 Hummingbot paper dry run 导出的事件 JSONL，并生成 reconciliation/session gate/package。",
                "" if has_acceptance_inputs else "需要先生成 Hummingbot Sandbox 准备报告。",
            ),
            WorkflowAction(
                "run_hummingbot_observation_review",
                "生成 Hummingbot Observation Review",
                "start_job",
                bool(export_acceptance),
                "paper_safe",
                "基于 export acceptance 和事件 JSONL 生成 Hummingbot paper 观察窗口复盘。",
                "" if export_acceptance else "需要先运行 Hummingbot Export Acceptance。",
            ),
        ),
        notes=(
            (f"Latest Web paper observation review: {paper_review.get('job_id', '')}" if paper_review else "No Web paper observation review."),
            (f"Latest sandbox prepare: {sandbox_prepare.get('job_id', '')}" if sandbox_prepare else "No Web sandbox prepare."),
            (f"Latest runtime preflight: {runtime_preflight.get('job_id', '')}" if runtime_preflight else "No Web runtime preflight."),
            (f"Latest direct paper handoff: {handoff.get('job_id', '')}" if handoff else "No Web direct paper handoff."),
            (f"Latest direct paper install: {install.get('job_id', '')}" if install else "No Web direct paper install."),
            (f"Latest paper event collection: {event_collection.get('job_id', '')}" if event_collection else "No Web paper event collection."),
            (f"Latest export acceptance: {export_acceptance.get('job_id', '')}" if export_acceptance else "No Web export acceptance."),
        ),
    )


def _live_readiness_step(repo_root: Path) -> WorkflowStep:
    activation = Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_2_live_activation_checklist.json")
    connector = Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_3_live_connector_preflight.json")
    activation_payload = _read_json(repo_root / activation)
    connector_payload = _read_json(repo_root / connector)
    decision = str(connector_payload.get("decision") or activation_payload.get("decision", "unknown"))
    return WorkflowStep(
        step_id="live_readiness",
        phase="Phase 6.1-6.3",
        title="Live 准入与连接器预检",
        business_goal="完成告警、凭据权限、allowlist、operator signoff 和 connector 字段脱敏预检。",
        status="completed" if decision == "live_connector_preflight_ready" else "attention_required",
        decision=decision,
        owner="risk",
        inputs=(WorkflowArtifact("Hummingbot paper review", Path("reports/hummingbot_sandbox/crypto_relative_strength_v1_phase_5_10_observation_review.json")),),
        outputs=(WorkflowArtifact("Activation checklist", activation), WorkflowArtifact("Connector preflight", connector),),
        actions=(
            WorkflowAction(
                "view_live_readiness",
                "查看 Live 门禁",
                "view_artifact",
                True,
                "read_only",
                "查看 live activation checklist 和 connector preflight。",
            ),
            WorkflowAction(
                "generate_external_alert_outbox",
                "生成外部告警",
                "start_job",
                True,
                "operator_safe",
                "生成标准化外部告警 payload/outbox；不直接发送 webhook。",
            ),
        ),
    )


def _first_live_batch_step(repo_root: Path) -> WorkflowStep:
    package = Path(
        "reports/live_readiness/"
        "crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/"
        "package.json"
    )
    runner = Path(
        "reports/live_readiness/"
        "crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/"
        "package.json"
    )
    payload = _read_json(repo_root / runner)
    decision = str(payload.get("decision", "unknown"))
    return WorkflowStep(
        step_id="first_live_batch",
        phase="Phase 6.4-6.6",
        title="首次小资金 Live Batch",
        business_goal="在 50 USDT 低资金 cap 内生成候选订单和一次性 Hummingbot live runner。",
        status="completed" if decision == "live_one_batch_runner_ready" else "attention_required",
        decision=decision,
        owner="operator",
        inputs=(WorkflowArtifact("Candidate order package", package),),
        outputs=(WorkflowArtifact("One-batch runner package", runner),),
        actions=(
            WorkflowAction(
                "view_first_live_batch",
                "查看首批订单包",
                "view_artifact",
                True,
                "read_only",
                "查看候选订单和 one-shot runner package。",
            ),
            WorkflowAction(
                "generate_live_execution_package",
                "生成 Live 执行申请包",
                "start_job",
                True,
                "live_package_only",
                "生成候选 live orders 和风险 checklist；不生成 runner，不提交订单。",
            ),
            WorkflowAction(
                "run_live_batch",
                "启动 Live Runner",
                "blocked_live_action",
                False,
                "live_blocked",
                "Web 第一版不提供实盘启动能力。",
                "必须在独立人工流程中审批和启动；Web 不暴露 live runner。",
            ),
        ),
    )


def _post_trade_step(post_trade: dict[str, Any]) -> WorkflowStep:
    return WorkflowStep(
        step_id="post_trade_reconciliation",
        phase="Phase 6.7",
        title="成交后对账",
        business_goal="核对 live event、Hummingbot DB fill、余额 delta、风险 cap、日报和税务基础导出。",
        status="completed" if str(post_trade.get("status", "")).startswith("live_post_trade_reconciled") else "attention_required",
        decision=str(post_trade.get("status", "unknown")),
        owner="risk",
        inputs=(WorkflowArtifact("Live event log", Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/normalized_live_trades.jsonl"), "ledger"),),
        outputs=(WorkflowArtifact("Post-trade report", POST_TRADE_REPORT_PATH), WorkflowArtifact("Trade tax export", Path("reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/trade_tax_export.csv"), "csv"),),
        actions=(
            WorkflowAction(
                "view_post_trade",
                "查看对账报告",
                "view_artifact",
                True,
                "read_only",
                "查看成交后对账、日报和税务基础导出。",
            ),
            WorkflowAction(
                "generate_live_post_trade_report",
                "生成 Live Post-trade 复盘",
                "start_job",
                True,
                "operator_safe",
                "读取 live event、Hummingbot DB 和日志生成对账/税务基础导出；不提交订单。",
            ),
        ),
    )


def _cooldown_step(cooldown: dict[str, Any]) -> WorkflowStep:
    cooldown_window = _dict(cooldown.get("cooldown_window"))
    elapsed = bool(cooldown_window.get("cooldown_elapsed", False))
    return WorkflowStep(
        step_id="cooldown_review",
        phase="Phase 6.8",
        title="Live 冷却复盘",
        business_goal="确认 runner 已停止、配置已 disarm、open orders 清理、扩容仍被禁止。",
        status="active" if not elapsed else "completed",
        decision=str(cooldown.get("status", "unknown")),
        owner="operator",
        inputs=(WorkflowArtifact("Post-trade report", POST_TRADE_REPORT_PATH),),
        outputs=(WorkflowArtifact("Cooldown review", COOLDOWN_REPORT_PATH),),
        actions=(
            WorkflowAction(
                "view_cooldown",
                "查看冷却复盘",
                "view_artifact",
                True,
                "read_only",
                "查看 cooldown 状态和 recommended actions。",
            ),
            WorkflowAction(
                "generate_live_cooldown_review",
                "生成冷却复盘",
                "start_job",
                True,
                "operator_safe",
                "复跑 Phase 6.8 cooldown review，确认 runner 停止、配置 disarm 和 open orders 检查。",
            ),
        ),
        notes=(f"Next review not before: {cooldown_window.get('next_review_not_before', '')}",),
    )


def _closure_step(closure: dict[str, Any]) -> WorkflowStep:
    return WorkflowStep(
        step_id="initial_closure",
        phase="Phase 6.9",
        title="初始闭环与仓位生命周期",
        business_goal="冻结 v0 初始闭环证据，并确认 BTC 仓位继续观察或另行审批退出。",
        status="completed" if str(closure.get("status", "")).startswith("initial_v0_flow_closed") else "attention_required",
        decision=str(closure.get("status", "unknown")),
        owner="operator",
        inputs=(WorkflowArtifact("Cooldown review", COOLDOWN_REPORT_PATH),),
        outputs=(WorkflowArtifact("Initial closure", CLOSURE_REPORT_PATH),),
        actions=(
            WorkflowAction(
                "view_initial_closure",
                "查看闭环报告",
                "view_artifact",
                True,
                "read_only",
                "查看初始闭环、下一次 live decision 和持仓生命周期计划。",
            ),
            WorkflowAction(
                "generate_live_initial_closure_report",
                "生成初始闭环报告",
                "start_job",
                True,
                "operator_safe",
                "基于 post-trade 和 cooldown 复盘生成 Phase 6.9 初始闭环与持仓生命周期报告。",
            ),
            WorkflowAction(
                "generate_live_position_exit_plan",
                "生成仓位退出计划",
                "start_job",
                True,
                "live_plan_only",
                "生成真实仓位退出计划和审批清单；不生成 runner，不提交 sell order。",
            ),
        ),
    )


def _active_step_id(*, next_live_decision: str, initial_flow_closed: bool) -> str:
    if next_live_decision == "NO_GO_COOLDOWN_ACTIVE":
        return "cooldown_review"
    if initial_flow_closed:
        return "initial_closure"
    return "data_layer"


def _readiness_evidence_blocked_reason(
    *,
    candidate_job_id: str,
    has_candidate_walk_forward: bool,
    has_candidate_capacity: bool,
) -> str:
    if not candidate_job_id:
        return "需要先在研究阶段确认候选回测。"
    if not has_candidate_walk_forward:
        return "需要先生成当前候选的 Walk-forward 证据。"
    if not has_candidate_capacity:
        return "需要先生成当前候选的 Capacity Stress 证据。"
    return ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _latest_jobs_by_action(
    jobs: Iterable[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    latest: dict[str, Mapping[str, object]] = {}
    for job in jobs:
        action_id = str(job.get("action_id", ""))
        if not action_id:
            continue
        current = latest.get(action_id)
        if current is None or str(job.get("created_at", "")) > str(current.get("created_at", "")):
            latest[action_id] = job
    return latest


def _compact_job(job: Mapping[str, object]) -> dict[str, object]:
    return {
        "job_id": str(job.get("job_id", "")),
        "action_id": str(job.get("action_id", "")),
        "label": str(job.get("label", "")),
        "status": str(job.get("status", "")),
        "created_at": str(job.get("created_at", "")),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "return_code": job.get("return_code"),
        "parameters": _dict(job.get("parameters")),
        "artifacts": _dict(job.get("artifacts")),
        "result_summary": job.get("result_summary"),
    }


def _runtime_alert_for_job(
    action: WorkflowAction,
    job: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if job is None:
        return None
    status = str(job.get("status", ""))
    definition = JOB_ALERT_DEFINITIONS.get(status)
    if definition is None:
        return None
    severity, title = definition
    job_id = str(job.get("job_id", ""))
    return {
        "severity": severity,
        "title": title,
        "message": f"{action.label} latest job is {status}: {job_id}",
        "action_id": action.action_id,
        "action_label": action.label,
        "job_id": job_id,
        "job_status": status,
        "created_at": str(job.get("created_at", "")),
    }


def _runtime_status(alerts: list[object]) -> str:
    severities = {
        str(alert.get("severity", ""))
        for alert in alerts
        if isinstance(alert, dict)
    }
    if "error" in severities:
        return "error"
    if "warning" in severities:
        return "warning"
    return "ok"
