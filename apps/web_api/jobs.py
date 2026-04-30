"""Whitelisted local job runner for paper-safe web actions."""

from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Mapping

from apps.web_api.backtest_candidates import BACKTEST_CANDIDATE_PATH
from apps.web_api.backtest_candidates import read_backtest_candidate
from apps.web_api.readiness_disposition_state import disposition_resolution
from apps.web_api.readiness_disposition_state import read_recorded_disposition
from apps.web_api.status import REPO_ROOT


JobStatus = str
JOB_METADATA_FILENAME = "job.json"
JOB_QUEUE_STATE_PATH = Path("reports/web_reviews/job_queue.json")
ACTIVE_JOB_STATUSES = {"queued", "running", "cancel_requested"}
JOB_TIMEOUT_SECONDS = 600
BACKTEST_JOB_ACTION_IDS = {"run_backtest", "run_recommended_backtest"}


@dataclass(frozen=True, slots=True)
class JobSpec:
    action_id: str
    label: str
    command: tuple[str, ...]
    output_dir: Path
    artifacts: dict[str, str]
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class JobParameterSpec:
    name: str
    label: str
    input_type: str
    default: object
    help: str
    required: bool = True
    options: tuple[tuple[str, str], ...] = ()
    min_value: str | None = None
    max_value: str | None = None
    step: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "input_type": self.input_type,
            "default": self.default,
            "help": self.help,
            "required": self.required,
            "options": [{"label": label, "value": value} for label, value in self.options],
            "min": self.min_value,
            "max": self.max_value,
            "step": self.step,
        }


@dataclass(slots=True)
class JobRecord:
    job_id: str
    action_id: str
    label: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    command: tuple[str, ...]
    cwd: Path
    output_dir: Path
    artifacts: dict[str, str]
    parameters: dict[str, object]
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "action_id": self.action_id,
            "label": self.label,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "command": list(self.command),
            "cwd": str(self.cwd),
            "output_dir": str(self.output_dir),
            "artifacts": self.artifacts,
            "parameters": self.parameters,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
        }


class JobStore:
    def __init__(self, repo_root: Path = REPO_ROOT) -> None:
        self._repo_root = repo_root
        self._jobs: dict[str, JobRecord] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._lock = threading.Lock()

    def list_jobs(self) -> tuple[JobRecord, ...]:
        with self._lock:
            return tuple(sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True))

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start_job(self, action_id: str, parameters: Mapping[str, object] | None = None) -> JobRecord:
        job_id = _new_job_id(action_id)
        spec = build_job_spec(
            action_id=action_id,
            job_id=job_id,
            repo_root=self._repo_root,
            parameters=parameters,
        )
        record = JobRecord(
            job_id=job_id,
            action_id=action_id,
            label=spec.label,
            status="queued",
            created_at=datetime.now(tz=UTC),
            started_at=None,
            completed_at=None,
            command=spec.command,
            cwd=self._repo_root,
            output_dir=spec.output_dir,
            artifacts=spec.artifacts,
            parameters=spec.parameters,
        )
        with self._lock:
            active_job = _active_job_for_action(self._jobs.values(), action_id)
            if active_job is not None:
                raise ValueError(f"active job already exists for {action_id}: {active_job.job_id}")
            self._jobs[job_id] = record
        record.output_dir.mkdir(parents=True, exist_ok=True)
        _write_job_metadata(record)
        self._write_queue_state()
        thread = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        thread.start()
        return record

    def cancel_job(self, job_id: str) -> JobRecord | None:
        process: subprocess.Popen[str] | None = None
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            if record.status not in ACTIVE_JOB_STATUSES:
                raise ValueError(f"job is not cancelable in status: {record.status}")
            record.status = "cancel_requested"
            record.error = "Cancellation requested by operator."
            process = self._processes.get(job_id)
            _write_job_metadata(record)
            self._write_queue_state_unlocked()

        if process is not None and process.poll() is None:
            process.terminate()
        return record

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            if record.status == "cancel_requested":
                record.status = "canceled"
                record.completed_at = datetime.now(tz=UTC)
                _write_job_metadata(record)
                self._write_queue_state_unlocked()
                return
            record.status = "running"
            record.started_at = datetime.now(tz=UTC)
            _write_job_metadata(record)
            self._write_queue_state_unlocked()
        try:
            record.output_dir.mkdir(parents=True, exist_ok=True)
            process = subprocess.Popen(
                record.command,
                cwd=record.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with self._lock:
                self._processes[job_id] = process
                cancel_requested = record.status == "cancel_requested"
            if cancel_requested and process.poll() is None:
                process.terminate()

            try:
                stdout, stderr = process.communicate(timeout=JOB_TIMEOUT_SECONDS)
                return_code = process.returncode
                timed_out = False
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return_code = process.returncode
                timed_out = True

            with self._lock:
                self._processes.pop(job_id, None)
                record.return_code = return_code
                record.stdout = stdout[-12000:]
                record.stderr = stderr[-12000:]
                if timed_out:
                    record.status = "timed_out"
                    record.error = f"Job exceeded timeout of {JOB_TIMEOUT_SECONDS} seconds."
                elif record.status == "cancel_requested":
                    record.status = "canceled"
                    if not record.error:
                        record.error = "Canceled by operator."
                else:
                    record.status = "succeeded" if return_code == 0 else "failed"
                record.completed_at = datetime.now(tz=UTC)
                _write_job_metadata(record)
                self._write_queue_state_unlocked()
        except Exception as exc:  # pragma: no cover - defensive for runtime failures
            with self._lock:
                self._processes.pop(job_id, None)
                record.status = "failed"
                record.error = str(exc)
                record.completed_at = datetime.now(tz=UTC)
                _write_job_metadata(record)
                self._write_queue_state_unlocked()

    def _write_queue_state(self) -> None:
        with self._lock:
            self._write_queue_state_unlocked()

    def _write_queue_state_unlocked(self) -> None:
        persist_job_queue_state(tuple(self._jobs.values()), repo_root=self._repo_root)


job_store = JobStore()


STRATEGY_OPTIONS: dict[str, str] = {
    "crypto_relative_strength_v1": "strategies/crypto_relative_strength_v1",
    "crypto_momentum_v1": "strategies/crypto_momentum_v1",
}
CSV_INT_PARAMETERS = {
    "fast_windows",
    "slow_windows",
    "lookback_windows",
    "rotation_top_n_values",
}
CSV_DECIMAL_PARAMETERS = {
    "min_momentum",
    "min_trend_strengths",
}
CSV_OPTIONAL_DECIMAL_PARAMETERS = {"max_volatility"}
INT_PARAMETER_NAMES = {
    "cycles",
    "train_months",
    "test_months",
    "step_months",
    "data_refresh_overlap_bars",
    "data_refresh_bootstrap_bars",
    "refresh_overlap_bars",
    "refresh_bootstrap_bars",
    "observation_min_runtime_seconds",
    "heartbeat_interval_seconds",
    "balance_snapshot_interval_seconds",
    "event_collect_max_lines",
}
SCAN_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "crypto_relative_strength_v1": {
        "conservative": {
            "lookback_windows": "72,108",
            "rotation_top_n_values": "1,2",
            "min_momentum": "0,0.02",
        },
        "balanced": {
            "lookback_windows": "24,48,72,108,144",
            "rotation_top_n_values": "1,2,3",
            "min_momentum": "0,0.02,0.05",
        },
        "aggressive": {
            "lookback_windows": "12,24,36,48,72,108,144",
            "rotation_top_n_values": "1,2,3",
            "min_momentum": "0,0.01,0.02,0.05",
        },
    },
    "crypto_momentum_v1": {
        "conservative": {
            "fast_windows": "24,36",
            "slow_windows": "96,144",
            "min_trend_strengths": "0",
            "max_volatility": "none",
        },
        "balanced": {
            "fast_windows": "12,24,36",
            "slow_windows": "72,96,144",
            "min_trend_strengths": "0",
            "max_volatility": "none",
        },
        "aggressive": {
            "fast_windows": "8,12,24,36,48",
            "slow_windows": "48,72,96,144,192",
            "min_trend_strengths": "0,0.01",
            "max_volatility": "none,0.04",
        },
    },
}

ACTION_PARAMETER_DEFINITIONS: dict[str, tuple[JobParameterSpec, ...]] = {
    "refresh_market_data": (
        JobParameterSpec(
            "strategy_id",
            "策略",
            "select",
            "crypto_relative_strength_v1",
            "选择要刷新行情覆盖的策略。",
            options=(
                ("Crypto Relative Strength V1", "crypto_relative_strength_v1"),
                ("Crypto Momentum V1", "crypto_momentum_v1"),
            ),
        ),
        JobParameterSpec(
            "db",
            "SQLite 数据库",
            "text",
            "data/warehouse/quant_system.sqlite",
            "要写入 K 线的 SQLite warehouse。",
        ),
        JobParameterSpec(
            "data_refresh_overlap_bars",
            "刷新重叠 K 线数",
            "number",
            2,
            "刷新时重复拉取最近多少根已闭合 K 线。",
            min_value="0",
            max_value="48",
            step="1",
        ),
        JobParameterSpec(
            "data_refresh_bootstrap_bars",
            "初始化 K 线数",
            "number",
            200,
            "本地无该交易对数据时首次拉取多少根 K 线。",
            min_value="50",
            max_value="2000",
            step="10",
        ),
        JobParameterSpec(
            "data_refresh_close_delay_seconds",
            "闭合延迟秒数",
            "number",
            "60",
            "距离当前 interval 边界后延多久才认为 K 线已闭合。",
            min_value="0",
            max_value="600",
            step="5",
        ),
        JobParameterSpec(
            "insecure_skip_tls_verify",
            "跳过 TLS 校验",
            "checkbox",
            False,
            "仅用于本机证书链异常时的公开行情请求，不涉及任何交易密钥。",
            required=False,
        ),
    ),
    "query_strategy_data_quality": (
        JobParameterSpec(
            "strategy_id",
            "策略",
            "select",
            "crypto_relative_strength_v1",
            "选择要检查行情覆盖的策略。",
            options=(
                ("Crypto Relative Strength V1", "crypto_relative_strength_v1"),
                ("Crypto Momentum V1", "crypto_momentum_v1"),
            ),
        ),
        JobParameterSpec(
            "db",
            "SQLite 数据库",
            "text",
            "data/warehouse/quant_system.sqlite",
            "要查询的 SQLite warehouse。",
        ),
    ),
    "run_backtest": (
        JobParameterSpec(
            "strategy_id",
            "策略",
            "select",
            "crypto_relative_strength_v1",
            "选择已接入 backtest.yml 的策略。",
            options=(
                ("Crypto Relative Strength V1", "crypto_relative_strength_v1"),
                ("Crypto Momentum V1", "crypto_momentum_v1"),
            ),
        ),
        JobParameterSpec("start", "开始日期", "date", "2023-01-01", "回测开始日期，UTC，包含当天。"),
        JobParameterSpec("end", "结束日期", "date", "2026-01-01", "回测结束日期，UTC，不包含当天。"),
        JobParameterSpec(
            "initial_equity",
            "初始资金",
            "number",
            "10000",
            "回测初始权益，单位使用策略配置中的计价资产。",
            min_value="100",
            max_value="100000000",
            step="100",
        ),
    ),
    "run_parameter_scan": (
        JobParameterSpec(
            "strategy_id",
            "策略",
            "select",
            "crypto_relative_strength_v1",
            "选择要扫描的策略。相对强弱策略使用 lookback/top_n 参数；动量策略使用 fast/slow 参数。",
            options=(
                ("Crypto Relative Strength V1", "crypto_relative_strength_v1"),
                ("Crypto Momentum V1", "crypto_momentum_v1"),
            ),
        ),
        JobParameterSpec(
            "scan_template",
            "扫描模板",
            "select",
            "balanced",
            "选择保守、平衡、激进模板；选择自定义时才使用下方手动参数。",
            options=(
                ("平衡", "balanced"),
                ("保守", "conservative"),
                ("激进", "aggressive"),
                ("自定义", "custom"),
            ),
        ),
        JobParameterSpec("fast_windows", "快线窗口", "text", "12,24,36", "动量策略使用，逗号分隔。"),
        JobParameterSpec("slow_windows", "慢线窗口", "text", "72,96,144", "动量策略使用，逗号分隔，必须大于快线。"),
        JobParameterSpec("lookback_windows", "轮动 Lookback", "text", "24,48,72,108,144", "相对强弱策略使用，逗号分隔。"),
        JobParameterSpec("rotation_top_n_values", "轮动 Top N", "text", "1,2,3", "相对强弱策略使用，逗号分隔。"),
        JobParameterSpec("min_momentum", "最小动量", "text", "0,0.02,0.05", "相对强弱策略使用，逗号分隔。"),
        JobParameterSpec("min_trend_strengths", "趋势过滤", "text", "0", "动量策略可选，逗号分隔。"),
        JobParameterSpec("max_volatility", "波动率上限", "text", "none", "动量策略可选，逗号分隔；none 表示关闭。"),
        JobParameterSpec(
            "selection_mode",
            "排序模式",
            "select",
            "risk_adjusted",
            "return_first 按收益优先；risk_adjusted 先看门槛和风险调整分。",
            options=(("Risk Adjusted", "risk_adjusted"), ("Return First", "return_first")),
        ),
        JobParameterSpec(
            "selection_min_return",
            "最低收益",
            "number",
            "0",
            "risk_adjusted 模式下的最低收益门槛。",
            min_value="-1",
            max_value="10",
            step="0.01",
        ),
        JobParameterSpec(
            "selection_max_drawdown",
            "最大回撤",
            "number",
            "0.20",
            "risk_adjusted 模式下的最大回撤门槛。",
            min_value="0",
            max_value="1",
            step="0.01",
        ),
        JobParameterSpec(
            "selection_max_turnover",
            "最大换手",
            "number",
            "45",
            "risk_adjusted 模式下的最大换手门槛。",
            min_value="0",
            max_value="10000",
            step="1",
        ),
        JobParameterSpec(
            "selection_max_tail_loss",
            "最大尾部亏损",
            "number",
            "0.08",
            "risk_adjusted 模式下的尾部亏损门槛。",
            min_value="0",
            max_value="1",
            step="0.01",
        ),
    ),
    "run_recommended_backtest": (
        JobParameterSpec("scan_job_id", "扫描任务", "text", "", "参数扫描任务 ID。"),
        JobParameterSpec("run_id", "推荐组合", "text", "", "扫描结果中的 run_id。"),
    ),
    "run_candidate_walk_forward": (
        JobParameterSpec("start", "验证开始日期", "date", "2023-01-01", "Walk-forward 开始日期，UTC。"),
        JobParameterSpec("end", "验证结束日期", "date", "2026-01-01", "Walk-forward 结束日期，UTC。"),
        JobParameterSpec(
            "train_months",
            "训练月数",
            "number",
            6,
            "每个 fold 的训练窗口长度。",
            min_value="1",
            max_value="36",
            step="1",
        ),
        JobParameterSpec(
            "test_months",
            "测试月数",
            "number",
            3,
            "每个 fold 的测试窗口长度。",
            min_value="1",
            max_value="12",
            step="1",
        ),
        JobParameterSpec(
            "step_months",
            "步进月数",
            "number",
            3,
            "相邻 fold 的步进长度。",
            min_value="1",
            max_value="12",
            step="1",
        ),
    ),
    "run_candidate_capacity_stress": (
        JobParameterSpec("start", "压力开始日期", "date", "2023-01-01", "容量压力回测开始日期，UTC。"),
        JobParameterSpec("end", "压力结束日期", "date", "2026-01-01", "容量压力回测结束日期，UTC。"),
        JobParameterSpec(
            "initial_equity",
            "压力资金",
            "number",
            "1000000",
            "容量压力测试使用的初始资金。",
            min_value="100",
            max_value="1000000000",
            step="1000",
        ),
    ),
    "generate_paper_readiness": (
        JobParameterSpec(
            "min_capacity_equity",
            "最低容量资金",
            "number",
            "100000",
            "容量压力测试必须达到的最低权益。",
            min_value="0",
            max_value="1000000000",
            step="1000",
        ),
        JobParameterSpec(
            "max_worst_return_loss",
            "最大最差收益亏损",
            "number",
            "0.05",
            "允许的最差 fold 收益亏损上限，例如 0.05 表示 5%。",
            min_value="0",
            max_value="1",
            step="0.01",
        ),
        JobParameterSpec(
            "max_worst_drawdown",
            "最大最差回撤",
            "number",
            "0.12",
            "允许的最差 fold 回撤上限。",
            min_value="0",
            max_value="1",
            step="0.01",
        ),
        JobParameterSpec(
            "max_worst_tail_loss",
            "最大尾部亏损",
            "number",
            "0.06",
            "允许的最差 fold 尾部亏损上限。",
            min_value="0",
            max_value="1",
            step="0.01",
        ),
    ),
    "run_paper_smoke": (
        JobParameterSpec(
            "account_id",
            "Paper 账户",
            "text",
            "web-paper-smoke",
            "只用于本地 paper ledger 的账户标识。",
        ),
        JobParameterSpec(
            "initial_equity",
            "初始资金",
            "number",
            "2000",
            "Paper smoke 初始权益。",
            min_value="100",
            max_value="10000000",
            step="100",
        ),
        JobParameterSpec(
            "cycles",
            "Cycle 数",
            "number",
            1,
            "本地 paper observation 执行轮数；Web smoke 限制在 1-5。",
            min_value="1",
            max_value="5",
            step="1",
        ),
        JobParameterSpec(
            "interval_seconds",
            "Cycle 间隔秒数",
            "number",
            "0",
            "每轮 paper observation 之间的等待秒数；本地 smoke 默认不等待。",
            min_value="0",
            max_value="300",
            step="1",
        ),
        JobParameterSpec(
            "refresh_market_data",
            "运行前刷新行情",
            "checkbox",
            False,
            "每个 cycle 前从 Binance 公共接口刷新最近 K 线。",
            required=False,
        ),
        JobParameterSpec(
            "refresh_overlap_bars",
            "刷新重叠 K 线数",
            "number",
            2,
            "刷新行情时重复拉取最近多少根已闭合 K 线。",
            min_value="1",
            max_value="24",
            step="1",
        ),
        JobParameterSpec(
            "refresh_bootstrap_bars",
            "初始化 K 线数",
            "number",
            200,
            "某个交易对本地无行情时的首次拉取 K 线数量。",
            min_value="50",
            max_value="1000",
            step="10",
        ),
        JobParameterSpec(
            "refresh_close_delay_seconds",
            "闭合延迟秒数",
            "number",
            "60",
            "刷新行情时，距离当前 interval 边界后延多久才认为 K 线已闭合。",
            min_value="0",
            max_value="600",
            step="5",
        ),
        JobParameterSpec(
            "allow_readiness_warnings",
            "允许 readiness warning",
            "checkbox",
            True,
            "允许 paper_ready_with_warnings 进入本地 smoke。",
            required=False,
        ),
    ),
    "generate_paper_observation_review": (
        JobParameterSpec(
            "min_duration_hours",
            "最小观察小时数",
            "number",
            "0",
            "Web smoke 复盘默认允许短观察；正式 24h 复盘可改为 23.5。",
            min_value="0",
            max_value="168",
            step="0.5",
        ),
        JobParameterSpec(
            "min_ok_cycle_ratio",
            "最小 OK 周期比例",
            "number",
            "1",
            "允许进入下一阶段的 OK cycle 比例。",
            min_value="0",
            max_value="1",
            step="0.01",
        ),
        JobParameterSpec(
            "max_drawdown",
            "最大 Paper 回撤",
            "number",
            "0.02",
            "Paper observation 复盘的回撤警戒线。",
            min_value="0",
            max_value="1",
            step="0.01",
        ),
    ),
    "run_hummingbot_sandbox_prepare": (
        JobParameterSpec(
            "connector_name",
            "Hummingbot Paper Connector",
            "text",
            "binance_paper_trade",
            "Hummingbot sandbox/paper connector 名称；禁止 live connector。",
        ),
        JobParameterSpec(
            "controller_name",
            "Controller 名称",
            "text",
            "quant_system_sandbox_order_controller",
            "生成 sandbox manifest 时使用的 controller 名称。",
        ),
        JobParameterSpec(
            "allow_warnings",
            "允许复盘 warning",
            "checkbox",
            True,
            "允许 sandbox_ready_with_warnings 继续生成 Hummingbot paper manifest。",
            required=False,
        ),
    ),
    "run_hummingbot_runtime_preflight": (
        JobParameterSpec(
            "scan_roots",
            "扫描目录",
            "text",
            "../hummingbot-api/bots,../hummingbot/conf",
            "逗号或换行分隔的 Hummingbot 挂载目录；只扫描配置，不启动服务。",
        ),
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_runtime_preflight",
            "本次 runtime preflight 的标识。",
        ),
        JobParameterSpec(
            "expected_connector",
            "期望 Paper Connector",
            "text",
            "binance_paper_trade",
            "期望存在的 Hummingbot paper connector。",
        ),
    ),
    "run_hummingbot_cli_direct_paper_handoff": (
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_direct_paper_handoff",
            "Hummingbot CLI direct paper handoff 的 session 标识。",
        ),
        JobParameterSpec(
            "hummingbot_root",
            "Hummingbot Root",
            "text",
            "../hummingbot",
            "Hummingbot CLI 挂载根目录；本动作只生成文件和 install target，不启动 Hummingbot。",
        ),
        JobParameterSpec(
            "allow_warnings",
            "允许 preflight warning",
            "checkbox",
            True,
            "允许 runtime preflight warning 继续生成 direct paper handoff。",
            required=False,
        ),
        JobParameterSpec(
            "event_log_path",
            "容器内事件日志路径",
            "text",
            "/home/hummingbot/data/quant_system_web_hummingbot_events.jsonl",
            "Hummingbot 容器内 JSONL 事件输出路径。",
        ),
        JobParameterSpec(
            "script_config_name",
            "Script Config 文件名",
            "text",
            "quant_system_web_direct_paper.yml",
            "生成给 Hummingbot CLI 使用的 script config 文件名。",
        ),
        JobParameterSpec(
            "observation_min_runtime_seconds",
            "最短观察秒数",
            "number",
            0,
            "Hummingbot 脚本提交订单后至少保留观察的秒数。",
            min_value="0",
            max_value="86400",
            step="60",
        ),
        JobParameterSpec(
            "heartbeat_interval_seconds",
            "心跳秒数",
            "number",
            60,
            "Hummingbot 事件日志 heartbeat 间隔。",
            min_value="10",
            max_value="3600",
            step="10",
        ),
        JobParameterSpec(
            "balance_snapshot_interval_seconds",
            "余额快照秒数",
            "number",
            300,
            "Hummingbot 事件日志余额快照间隔。",
            min_value="30",
            max_value="7200",
            step="30",
        ),
    ),
    "install_hummingbot_cli_direct_paper_files": (
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_direct_paper_install",
            "Hummingbot CLI direct paper 文件安装的 session 标识。",
        ),
        JobParameterSpec(
            "hummingbot_root",
            "Hummingbot Root",
            "text",
            "../hummingbot",
            "Hummingbot CLI 挂载根目录；只复制 paper script/config 文件，不启动 Hummingbot。",
        ),
        JobParameterSpec(
            "dry_run",
            "仅生成安装计划",
            "checkbox",
            False,
            "只检查源文件和目标路径，不实际复制文件。",
            required=False,
        ),
        JobParameterSpec(
            "overwrite",
            "允许覆盖",
            "checkbox",
            False,
            "目标文件已存在且内容不一致时，是否允许覆盖。",
            required=False,
        ),
        JobParameterSpec(
            "clean_event_log",
            "清理旧事件日志",
            "checkbox",
            False,
            "安装时删除同名旧 Hummingbot paper event JSONL，避免新旧 session 混淆。",
            required=False,
        ),
    ),
    "run_hummingbot_paper_session_control": (
        JobParameterSpec(
            "mode",
            "控制动作",
            "select",
            "start_plan",
            "生成启动命令、记录已启动、生成停止命令或记录已停止。",
            options=(
                ("生成启动命令", "start_plan"),
                ("记录已启动", "record_started"),
                ("生成停止命令", "stop_plan"),
                ("记录已停止", "record_stopped"),
            ),
        ),
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_hummingbot_paper_session",
            "Hummingbot paper session 的业务标识。",
        ),
        JobParameterSpec(
            "container_name",
            "容器名",
            "text",
            "quant-system-hummingbot-paper",
            "生成 docker start/stop 命令时使用的容器名。",
        ),
        JobParameterSpec(
            "hummingbot_image",
            "Hummingbot 镜像",
            "text",
            "hummingbot/hummingbot:latest",
            "生成 docker start 命令时使用的镜像。",
        ),
        JobParameterSpec(
            "operator_note",
            "操作备注",
            "text",
            "paper_session_control",
            "记录人工启动/停止时的备注。",
            required=False,
        ),
    ),
    "collect_hummingbot_paper_events": (
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_hummingbot_event_collect",
            "Hummingbot paper event collection 的业务标识。",
        ),
        JobParameterSpec(
            "source_path",
            "事件源路径",
            "text",
            "auto_from_session_state",
            "默认读取 session state 中记录的 event_log_host_path；也可手工指定 JSONL 路径。",
        ),
        JobParameterSpec(
            "event_collect_max_lines",
            "最大采集行数",
            "number",
            50000,
            "单次最多采集的 JSONL 行数。",
            min_value="1",
            max_value="1000000",
            step="1000",
        ),
    ),
    "run_hummingbot_export_acceptance": (
        JobParameterSpec(
            "events_jsonl",
            "Hummingbot 事件 JSONL",
            "text",
            "auto_latest_collected",
            "默认使用最新采集的 Hummingbot paper event JSONL；也可手工指定路径。",
        ),
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_export_acceptance",
            "本次 Hummingbot export acceptance 的 session 标识。",
        ),
        JobParameterSpec(
            "event_source",
            "事件来源",
            "select",
            "hummingbot_export",
            "真实 Hummingbot paper export 使用 hummingbot_export；仅回放数据使用 replay。",
            options=(("Hummingbot Export", "hummingbot_export"), ("Replay", "replay")),
        ),
        JobParameterSpec(
            "allow_warnings",
            "允许 warning",
            "checkbox",
            True,
            "允许 reconciliation/session gate/package warning 通过验收。",
            required=False,
        ),
        JobParameterSpec(
            "no_require_balance_event",
            "不强制余额事件",
            "checkbox",
            True,
            "当 Hummingbot paper export 没有余额事件时，允许跳过余额事件硬性要求。",
            required=False,
        ),
        JobParameterSpec(
            "starting_quote_balance",
            "起始 Quote 余额",
            "number",
            "0",
            "可选；大于 0 时用于余额对账。",
            min_value="0",
            max_value="1000000000",
            step="100",
        ),
        JobParameterSpec(
            "quote_asset",
            "Quote 资产",
            "text",
            "USDT",
            "余额对账使用的 quote asset。",
        ),
    ),
    "run_hummingbot_observation_review": (
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_hummingbot_observation_review",
            "Hummingbot paper observation review 的 session 标识。",
        ),
        JobParameterSpec(
            "target_window_hours",
            "目标观察小时数",
            "number",
            "2",
            "下一段 Hummingbot paper observation window 的目标小时数。",
            min_value="0.1",
            max_value="168",
            step="0.5",
        ),
        JobParameterSpec(
            "allow_warnings",
            "允许 acceptance warning",
            "checkbox",
            True,
            "允许上游 export acceptance warning 继续生成 observation review。",
            required=False,
        ),
    ),
    "generate_live_execution_package": (
        JobParameterSpec(
            "session_id",
            "Session ID",
            "text",
            "web_live_execution_package",
            "本次 Live 执行申请包的 session 标识。",
        ),
        JobParameterSpec(
            "activation_plan_json",
            "Activation Plan JSON",
            "text",
            "reports/live_readiness/crypto_relative_strength_v1_phase_6_4_first_live_batch_activation_plan_low_funds_50.json",
            "已审批的首批小资金 live activation plan。",
        ),
        JobParameterSpec(
            "market_data_refresh_json",
            "Market Data Refresh JSON",
            "text",
            "reports/live_readiness/crypto_relative_strength_v1_phase_6_5_market_data_refresh.json",
            "Phase 6.5 market data refresh 证据。",
        ),
        JobParameterSpec(
            "live_risk_yml",
            "Live Risk YAML",
            "text",
            "strategies/crypto_relative_strength_v1/risk.live.phase_6_2.yml",
            "严格 live risk 配置。",
        ),
        JobParameterSpec(
            "strategy_id",
            "策略",
            "select",
            "crypto_relative_strength_v1",
            "生成候选 live orders 的策略。",
            options=(
                ("Crypto Relative Strength V1", "crypto_relative_strength_v1"),
                ("Crypto Momentum V1", "crypto_momentum_v1"),
            ),
        ),
        JobParameterSpec(
            "db",
            "SQLite 数据库",
            "text",
            "data/warehouse/quant_system.sqlite",
            "用于读取最新信号 K 线的 SQLite warehouse。",
        ),
        JobParameterSpec(
            "allowed_pairs",
            "允许交易对",
            "text",
            "BTC-USDT,ETH-USDT",
            "逗号或换行分隔的候选交易对；只生成申请包，不提交订单。",
        ),
    ),
    "generate_live_post_trade_report": (
        JobParameterSpec("event_jsonl", "Live Event JSONL", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/normalized_live_trades.jsonl", "Live runner event JSONL。"),
        JobParameterSpec("sqlite_db", "Hummingbot SQLite DB", "text", "../hummingbot/data/hummingbot.sqlite", "Hummingbot live session SQLite DB。"),
        JobParameterSpec("log_file", "Hummingbot Log", "text", "../hummingbot/logs/hummingbot.log", "Hummingbot live session log 文件。"),
        JobParameterSpec("candidate_package_json", "Candidate Package JSON", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_5_candidate_live_batch_package_low_funds_50/package.json", "Phase 6.5 candidate package。"),
        JobParameterSpec("runner_package_json", "Runner Package JSON", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.json", "Phase 6.6 runner package。"),
        JobParameterSpec("session_id", "Session ID", "text", "web_live_post_trade", "Post-trade 复盘 session 标识。"),
        JobParameterSpec("account_id", "账户", "text", "binance-main-spot", "账户标签。"),
        JobParameterSpec("strategy_id", "策略", "select", "crypto_relative_strength_v1", "策略。", options=(("Crypto Relative Strength V1", "crypto_relative_strength_v1"), ("Crypto Momentum V1", "crypto_momentum_v1"))),
        JobParameterSpec("cad_fx_rate", "CAD FX", "number", "1", "验证用 CAD FX rate。", min_value="0", max_value="10", step="0.0001"),
        JobParameterSpec("fx_source", "FX 来源", "text", "validation_only_not_tax_filing", "FX 来源标签。"),
        JobParameterSpec("runner_container", "Runner 容器", "text", "none", "容器名；填 none 跳过 docker 状态读取。", required=False),
    ),
    "generate_live_cooldown_review": (
        JobParameterSpec("post_trade_report_json", "Post-trade JSON", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.json", "Phase 6.7 post-trade report。"),
        JobParameterSpec("event_jsonl", "Live Event JSONL", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/normalized_live_trades.jsonl", "Live event JSONL。"),
        JobParameterSpec("runner_config_yml", "Runner Config YAML", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_6_live_one_batch_runner_low_funds_50/package.md", "Installed runner config 或 runner package 证据。"),
        JobParameterSpec("manual_open_orders_check_json", "人工 open orders 检查", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/manual_open_orders_check.json", "人工 open orders 检查 JSON。"),
        JobParameterSpec("session_id", "Session ID", "text", "web_live_cooldown", "Cooldown 复盘 session 标识。"),
        JobParameterSpec("minimum_cooldown_hours", "最短冷却小时", "number", "24", "最短冷却窗口。", min_value="0", max_value="720", step="1"),
        JobParameterSpec("runner_container", "Runner 容器", "text", "quant-phase-6-6-live-one-batch-low-funds-50", "Runner 容器名。"),
        JobParameterSpec("hummingbot_container", "Hummingbot 容器", "text", "hummingbot", "Hummingbot 容器名。"),
    ),
    "generate_live_initial_closure_report": (
        JobParameterSpec("post_trade_report_json", "Post-trade JSON", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_7_live_post_trade_low_funds_50/post_trade_report.json", "Phase 6.7 post-trade report。"),
        JobParameterSpec("cooldown_review_json", "Cooldown JSON", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_8_live_cooldown_review_low_funds_50/cooldown_review.json", "Phase 6.8 cooldown review。"),
        JobParameterSpec("session_id", "Session ID", "text", "web_live_initial_closure", "Initial closure session 标识。"),
    ),
    "generate_live_position_exit_plan": (
        JobParameterSpec("initial_closure_json", "Initial Closure JSON", "text", "reports/live_readiness/crypto_relative_strength_v1_phase_6_9_initial_closure_position_plan_low_funds_50/initial_closure_report.json", "Phase 6.9 initial closure report。"),
        JobParameterSpec("session_id", "Session ID", "text", "web_live_exit_plan", "退出计划 session 标识。"),
        JobParameterSpec("max_exit_notional", "最大退出名义金额", "number", "50", "退出计划的名义金额上限；只生成计划，不提交订单。", min_value="0", max_value="100000", step="1"),
        JobParameterSpec("exit_reason", "退出原因", "text", "operator_requested_exit_review", "退出计划原因。"),
    ),
    "generate_external_alert_outbox": (
        JobParameterSpec("channel", "告警通道", "text", "ops_webhook", "外部告警通道标签。"),
        JobParameterSpec("severity", "级别", "select", "WARN", "告警级别。", options=(("Info", "INFO"), ("Warn", "WARN"), ("Critical", "CRITICAL"))),
        JobParameterSpec("title", "标题", "text", "Quant System Alert", "告警标题。"),
        JobParameterSpec("message", "内容", "text", "Review quant-system workflow alerts.", "告警内容。"),
        JobParameterSpec("dispatch_enabled", "尝试发送", "checkbox", False, "当前 Web 只生成 outbox；发送需要独立 worker。", required=False),
    ),
}


def job_parameter_definitions(action_id: str) -> tuple[JobParameterSpec, ...]:
    return ACTION_PARAMETER_DEFINITIONS.get(action_id, ())


def build_job_spec(
    *,
    action_id: str,
    job_id: str,
    repo_root: Path = REPO_ROOT,
    parameters: Mapping[str, object] | None = None,
) -> JobSpec:
    normalized = normalize_job_parameters(action_id, parameters)
    output_dir = Path("reports/web_jobs") / job_id
    absolute_output_dir = repo_root / output_dir

    if action_id == "refresh_market_data":
        strategy_id = str(normalized["strategy_id"])
        output_json = output_dir / "market_data_refresh.json"
        command = [
            sys.executable,
            "-m",
            "packages.data.run_market_data_refresh",
            "--strategy-dir",
            STRATEGY_OPTIONS[strategy_id],
            "--db",
            str(normalized["db"]),
            "--output-json",
            str(output_json),
            "--overlap-bars",
            str(normalized["data_refresh_overlap_bars"]),
            "--bootstrap-bars",
            str(normalized["data_refresh_bootstrap_bars"]),
            "--close-delay-seconds",
            str(normalized["data_refresh_close_delay_seconds"]),
        ]
        if normalized["insecure_skip_tls_verify"]:
            command.append("--insecure-skip-tls-verify")
        return JobSpec(
            action_id=action_id,
            label="刷新公开行情",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "market_data_refresh_json": str(output_json),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "query_strategy_data_quality":
        strategy_id = str(normalized["strategy_id"])
        output_json = output_dir / "strategy_data_quality.json"
        return JobSpec(
            action_id=action_id,
            label="检查策略数据质量",
            command=(
                sys.executable,
                "-m",
                "packages.data.query_strategy_candles",
                "--strategy-dir",
                STRATEGY_OPTIONS[strategy_id],
                "--db",
                str(normalized["db"]),
                "--json",
                "--output-json",
                str(output_json),
            ),
            output_dir=absolute_output_dir,
            artifacts={
                "strategy_data_quality_json": str(output_json),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "run_backtest":
        strategy_id = str(normalized["strategy_id"])
        output = output_dir / f"{strategy_id}_backtest.json"
        return JobSpec(
            action_id=action_id,
            label="重新运行回测",
            command=(
                sys.executable,
                "-m",
                "packages.backtesting.run_backtest",
                "--strategy-dir",
                STRATEGY_OPTIONS[strategy_id],
                "--db",
                "data/warehouse/quant_system.sqlite",
                "--output",
                str(output),
                "--initial-equity",
                str(normalized["initial_equity"]),
                "--start",
                str(normalized["start"]),
                "--end",
                str(normalized["end"]),
            ),
            output_dir=absolute_output_dir,
            artifacts={
                "backtest_json": str(output),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "run_parameter_scan":
        strategy_id = str(normalized["strategy_id"])
        output = output_dir / f"{strategy_id}_parameter_scan.json"
        summary_csv = output_dir / f"{strategy_id}_parameter_scan.csv"
        command = [
            sys.executable,
            "-m",
            "packages.backtesting.run_parameter_scan",
            "--strategy-dir",
            STRATEGY_OPTIONS[strategy_id],
            "--db",
            "data/warehouse/quant_system.sqlite",
            "--output",
            str(output),
            "--summary-csv",
            str(summary_csv),
            "--experiment-id",
            job_id,
            "--selection-mode",
            str(normalized["selection_mode"]),
            "--selection-min-return",
            str(normalized["selection_min_return"]),
            "--selection-max-drawdown",
            str(normalized["selection_max_drawdown"]),
            "--selection-max-turnover",
            str(normalized["selection_max_turnover"]),
            "--selection-max-tail-loss",
            str(normalized["selection_max_tail_loss"]),
            "--top-n",
            "8",
        ]
        if strategy_id == "crypto_relative_strength_v1":
            command.extend(
                [
                    "--lookback-windows",
                    str(normalized["lookback_windows"]),
                    "--rotation-top-n-values",
                    str(normalized["rotation_top_n_values"]),
                    "--min-momentum",
                    str(normalized["min_momentum"]),
                ]
            )
        else:
            command.extend(
                [
                    "--fast-windows",
                    str(normalized["fast_windows"]),
                    "--slow-windows",
                    str(normalized["slow_windows"]),
                    "--min-trend-strengths",
                    str(normalized["min_trend_strengths"]),
                    "--max-volatility",
                    str(normalized["max_volatility"]),
                ]
            )
        return JobSpec(
            action_id=action_id,
            label="运行参数扫描",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "parameter_scan_json": str(output),
                "parameter_scan_csv": str(summary_csv),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "run_recommended_backtest":
        recommendation = _scan_recommendation(
            repo_root,
            scan_job_id=str(normalized["scan_job_id"]),
            run_id=str(normalized["run_id"]),
        )
        strategy_id = str(recommendation["strategy_id"])
        run_id = str(recommendation["run_id"])
        output = output_dir / f"{strategy_id}_{_safe_slug(run_id)}_backtest.json"
        command = [
            sys.executable,
            "-m",
            "packages.backtesting.run_backtest",
            "--strategy-dir",
            STRATEGY_OPTIONS[strategy_id],
            "--db",
            "data/warehouse/quant_system.sqlite",
            "--output",
            str(output),
        ]
        _append_recommended_backtest_overrides(command, _mapping(recommendation["parameters"]))
        parameters_with_recommendation = {
            **normalized,
            "strategy_id": strategy_id,
            "scan_rank": recommendation["rank"],
            "recommendation_parameters": recommendation["parameters"],
            "recommendation_metrics": recommendation["metrics"],
        }
        return JobSpec(
            action_id=action_id,
            label="按推荐运行回测",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "backtest_json": str(output),
                "source_parameter_scan_json": str(recommendation["artifact_path"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=parameters_with_recommendation,
        )

    if action_id == "run_candidate_walk_forward":
        candidate = _confirmed_backtest_candidate(repo_root)
        candidate_backtest = _load_candidate_backtest(repo_root, candidate)
        output_json = output_dir / "candidate_walk_forward.json"
        summary_csv = output_dir / "candidate_walk_forward.csv"
        command = [
            sys.executable,
            "-m",
            "packages.backtesting.run_walk_forward",
            "--strategy-dir",
            STRATEGY_OPTIONS[candidate["strategy_id"]],
            "--db",
            "data/warehouse/quant_system.sqlite",
            "--output",
            str(output_json),
            "--summary-csv",
            str(summary_csv),
            "--experiment-id",
            job_id,
            "--start",
            str(normalized["start"]),
            "--end",
            str(normalized["end"]),
            "--train-months",
            str(normalized["train_months"]),
            "--test-months",
            str(normalized["test_months"]),
            "--step-months",
            str(normalized["step_months"]),
            "--selection-mode",
            "risk_adjusted",
            "--selection-min-return",
            "0",
            "--selection-max-drawdown",
            "0.20",
            "--selection-max-turnover",
            "45",
            "--selection-max-tail-loss",
            "0.08",
        ]
        _append_candidate_walk_forward_grid(command, candidate["strategy_id"], _mapping(candidate_backtest.get("parameters")))
        parameters_with_candidate = {
            **normalized,
            "candidate_job_id": candidate["job_id"],
            "candidate_strategy_id": candidate["strategy_id"],
            "candidate_backtest_json": candidate["artifact_path"],
        }
        return JobSpec(
            action_id=action_id,
            label="生成候选 Walk-forward",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "walk_forward_json": str(output_json),
                "walk_forward_csv": str(summary_csv),
                "candidate_review_json": str(BACKTEST_CANDIDATE_PATH),
                "candidate_backtest_json": str(candidate["artifact_path"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=parameters_with_candidate,
        )

    if action_id == "run_candidate_capacity_stress":
        candidate = _confirmed_backtest_candidate(repo_root)
        candidate_backtest = _load_candidate_backtest(repo_root, candidate)
        output_json = output_dir / "candidate_capacity_stress.json"
        command = [
            sys.executable,
            "-m",
            "packages.backtesting.run_backtest",
            "--strategy-dir",
            STRATEGY_OPTIONS[candidate["strategy_id"]],
            "--db",
            "data/warehouse/quant_system.sqlite",
            "--output",
            str(output_json),
            "--initial-equity",
            str(normalized["initial_equity"]),
            "--start",
            str(normalized["start"]),
            "--end",
            str(normalized["end"]),
        ]
        _append_recommended_backtest_overrides(command, _mapping(candidate_backtest.get("parameters")))
        parameters_with_candidate = {
            **normalized,
            "candidate_job_id": candidate["job_id"],
            "candidate_strategy_id": candidate["strategy_id"],
            "candidate_backtest_json": candidate["artifact_path"],
        }
        return JobSpec(
            action_id=action_id,
            label="生成候选 Capacity Stress",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "capacity_stress_json": str(output_json),
                "candidate_review_json": str(BACKTEST_CANDIDATE_PATH),
                "candidate_backtest_json": str(candidate["artifact_path"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=parameters_with_candidate,
        )

    if action_id == "generate_paper_readiness":
        candidate = _confirmed_backtest_candidate(repo_root)
        _ensure_readiness_disposition_allows_rerun(repo_root, candidate)
        candidate_walk_forward = latest_candidate_walk_forward_evidence(repo_root, candidate)
        if not candidate_walk_forward:
            raise ValueError("需要先生成当前候选的 Walk-forward 证据。")
        walk_forward_json = Path(str(candidate_walk_forward["walk_forward_json"]))
        _ensure_readiness_evidence_exists(repo_root, walk_forward_json, "walk-forward")
        candidate_capacity = latest_candidate_capacity_stress_evidence(repo_root, candidate)
        if not candidate_capacity:
            raise ValueError("需要先生成当前候选的 Capacity Stress 证据。")
        capacity_stress_json = Path(str(candidate_capacity["capacity_stress_json"]))
        _ensure_readiness_evidence_exists(repo_root, capacity_stress_json, "capacity stress")
        output_json = output_dir / "paper_readiness.json"
        output_md = output_dir / "paper_readiness.md"
        runbook_md = output_dir / "risk_off_runbook.md"
        command = [
            sys.executable,
            "-m",
            "packages.reporting.run_paper_readiness_report",
            "--walk-forward-json",
            str(walk_forward_json),
        ]
        command.extend(["--capacity-stress-json", str(capacity_stress_json)])
        command.extend(
            [
                "--candidate-review-json",
                str(BACKTEST_CANDIDATE_PATH),
                "--candidate-backtest-json",
                str(candidate["artifact_path"]),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
                "--runbook-md",
                str(runbook_md),
                "--min-capacity-equity",
                str(normalized["min_capacity_equity"]),
                "--max-worst-return-loss",
                str(normalized["max_worst_return_loss"]),
                "--max-worst-drawdown",
                str(normalized["max_worst_drawdown"]),
                "--max-worst-tail-loss",
                str(normalized["max_worst_tail_loss"]),
            ]
        )
        parameters_with_candidate = {
            **normalized,
            "candidate_job_id": candidate["job_id"],
            "candidate_strategy_id": candidate["strategy_id"],
            "candidate_backtest_json": candidate["artifact_path"],
            "candidate_review_json": str(BACKTEST_CANDIDATE_PATH),
            "walk_forward_json": str(walk_forward_json),
            "walk_forward_source_job_id": str(candidate_walk_forward.get("job_id", "")),
            "capacity_stress_json": str(capacity_stress_json),
            "capacity_stress_source_job_id": str(candidate_capacity.get("job_id", "")),
        }
        return JobSpec(
            action_id=action_id,
            label="生成 Paper 准入",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "readiness_json": str(output_json),
                "readiness_md": str(output_md),
                "runbook_md": str(runbook_md),
                "candidate_review_json": str(BACKTEST_CANDIDATE_PATH),
                "candidate_backtest_json": str(candidate["artifact_path"]),
                "walk_forward_json": str(walk_forward_json),
                "capacity_stress_json": str(capacity_stress_json),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=parameters_with_candidate,
        )

    if action_id == "run_paper_smoke":
        readiness = latest_passed_paper_readiness(repo_root)
        if not readiness:
            raise ValueError("需要先生成通过的 Paper 准入报告。")
        ledger = output_dir / "paper_smoke_ledger.jsonl"
        observation = output_dir / "paper_smoke_observation.jsonl"
        summary = output_dir / "paper_smoke_summary.json"
        report = output_dir / "paper_smoke_report.md"
        command = [
            sys.executable,
            "-m",
            "packages.paper_trading.run_paper_observation",
            "--strategy-dir",
            "strategies/crypto_relative_strength_v1",
            "--db",
            "data/warehouse/quant_system.sqlite",
            "--readiness-json",
            str(readiness["readiness_json"]),
        ]
        if normalized["allow_readiness_warnings"]:
            command.append("--allow-readiness-warnings")
        if normalized["refresh_market_data"]:
            command.extend(
                [
                    "--refresh-market-data",
                    "--refresh-overlap-bars",
                    str(normalized["refresh_overlap_bars"]),
                    "--refresh-bootstrap-bars",
                    str(normalized["refresh_bootstrap_bars"]),
                    "--refresh-close-delay-seconds",
                    str(normalized["refresh_close_delay_seconds"]),
                ]
            )
        command.extend(
            [
                "--ledger",
                str(ledger),
                "--observation-log",
                str(observation),
                "--summary-json",
                str(summary),
                "--report-md",
                str(report),
                "--account-id",
                str(normalized["account_id"]),
                "--initial-equity",
                str(normalized["initial_equity"]),
                "--cycles",
                str(normalized["cycles"]),
                "--interval-seconds",
                str(normalized["interval_seconds"]),
            ]
        )
        return JobSpec(
            action_id=action_id,
            label="运行 Paper Smoke",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "ledger_jsonl": str(ledger),
                "observation_jsonl": str(observation),
                "summary_json": str(summary),
                "report_md": str(report),
                "readiness_json": str(readiness["readiness_json"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "readiness_job_id": readiness["job_id"],
                "readiness_status": readiness["status"],
                "candidate_job_id": readiness.get("candidate_job_id", ""),
            },
        )

    if action_id == "generate_paper_observation_review":
        paper_smoke = latest_paper_smoke_evidence(repo_root)
        if not paper_smoke:
            raise ValueError("需要先成功运行 Paper Smoke。")
        output_json = output_dir / "paper_observation_review.json"
        output_md = output_dir / "paper_observation_review.md"
        command = [
            sys.executable,
            "-m",
            "packages.reporting.run_paper_observation_review",
            "--observation-jsonl",
            str(paper_smoke["observation_jsonl"]),
            "--ledger-jsonl",
            str(paper_smoke["ledger_jsonl"]),
            "--initial-equity",
            str(paper_smoke["initial_equity"]),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
            "--min-duration-hours",
            str(normalized["min_duration_hours"]),
            "--min-ok-cycle-ratio",
            str(normalized["min_ok_cycle_ratio"]),
            "--max-drawdown",
            str(normalized["max_drawdown"]),
        ]
        if paper_smoke.get("readiness_json"):
            command.extend(["--readiness-json", str(paper_smoke["readiness_json"])])
        return JobSpec(
            action_id=action_id,
            label="生成 Paper 观察复盘",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "paper_observation_review_json": str(output_json),
                "paper_observation_review_md": str(output_md),
                "observation_jsonl": str(paper_smoke["observation_jsonl"]),
                "ledger_jsonl": str(paper_smoke["ledger_jsonl"]),
                "readiness_json": str(paper_smoke.get("readiness_json", "")),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "paper_smoke_job_id": paper_smoke["job_id"],
                "initial_equity": paper_smoke["initial_equity"],
            },
        )

    if action_id == "run_hummingbot_sandbox_prepare":
        review = latest_paper_observation_review(repo_root)
        if not review:
            raise ValueError("需要先生成 Paper 观察复盘。")
        manifest_json = output_dir / "hummingbot_sandbox_manifest.json"
        report_json = output_dir / "hummingbot_sandbox_prepare.json"
        report_md = output_dir / "hummingbot_sandbox_prepare.md"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_sandbox_prepare",
            "--review-json",
            str(review["review_json"]),
            "--ledger-jsonl",
            str(review["ledger_jsonl"]),
            "--connector-name",
            str(normalized["connector_name"]),
            "--controller-name",
            str(normalized["controller_name"]),
            "--manifest-json",
            str(manifest_json),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_md),
        ]
        if normalized["allow_warnings"]:
            command.append("--allow-warnings")
        return JobSpec(
            action_id=action_id,
            label="生成 Hummingbot Sandbox 准备",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "sandbox_manifest_json": str(manifest_json),
                "sandbox_prepare_json": str(report_json),
                "sandbox_prepare_md": str(report_md),
                "paper_observation_review_json": str(review["review_json"]),
                "ledger_jsonl": str(review["ledger_jsonl"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "paper_observation_review_job_id": review["job_id"],
            },
        )

    if action_id == "run_hummingbot_runtime_preflight":
        scan_roots = _split_scan_roots(str(normalized["scan_roots"]))
        if not scan_roots:
            raise ValueError("scan_roots must contain at least one path")
        output_json = output_dir / "hummingbot_runtime_preflight.json"
        output_md = output_dir / "hummingbot_runtime_preflight.md"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_runtime_preflight",
            "--session-id",
            str(normalized["session_id"]),
            "--expected-connector",
            str(normalized["expected_connector"]),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
        for root in scan_roots:
            command.extend(["--scan-root", root])
        return JobSpec(
            action_id=action_id,
            label="运行 Hummingbot Runtime Preflight",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "runtime_preflight_json": str(output_json),
                "runtime_preflight_md": str(output_md),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={**normalized, "scan_roots": ",".join(scan_roots)},
        )

    if action_id == "run_hummingbot_cli_direct_paper_handoff":
        sandbox = latest_hummingbot_sandbox_prepare(repo_root)
        if not sandbox:
            raise ValueError("需要先生成 Hummingbot Sandbox 准备。")
        preflight = latest_hummingbot_runtime_preflight(repo_root)
        if not preflight:
            raise ValueError("需要先运行 Hummingbot Runtime Preflight。")
        handoff_dir = output_dir / "direct_paper_handoff"
        script_config_name = str(normalized["script_config_name"])
        handoff_json = handoff_dir / "handoff.json"
        handoff_md = handoff_dir / "handoff.md"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_cli_direct_paper_handoff",
            "--manifest-json",
            str(sandbox["sandbox_manifest_json"]),
            "--runtime-preflight-json",
            str(preflight["runtime_preflight_json"]),
            "--output-dir",
            str(handoff_dir),
            "--session-id",
            str(normalized["session_id"]),
            "--hummingbot-root",
            str(normalized["hummingbot_root"]),
            "--event-log-path",
            str(normalized["event_log_path"]),
            "--script-config-name",
            script_config_name,
            "--observation-min-runtime-seconds",
            str(normalized["observation_min_runtime_seconds"]),
            "--heartbeat-interval-seconds",
            str(normalized["heartbeat_interval_seconds"]),
            "--balance-snapshot-interval-seconds",
            str(normalized["balance_snapshot_interval_seconds"]),
        ]
        if normalized["allow_warnings"]:
            command.append("--allow-warnings")
        return JobSpec(
            action_id=action_id,
            label="生成 Hummingbot CLI Direct Paper Handoff",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "handoff_json": str(handoff_json),
                "handoff_md": str(handoff_md),
                "script_source": str(handoff_dir / "scripts/quant_system_cli_paper_orders.py"),
                "script_config": str(handoff_dir / "conf/scripts" / script_config_name),
                "sandbox_manifest_json": str(sandbox["sandbox_manifest_json"]),
                "runtime_preflight_json": str(preflight["runtime_preflight_json"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "sandbox_prepare_job_id": sandbox["job_id"],
                "runtime_preflight_job_id": preflight["job_id"],
            },
        )

    if action_id == "install_hummingbot_cli_direct_paper_files":
        handoff = latest_hummingbot_cli_direct_paper_handoff(repo_root)
        if not handoff:
            raise ValueError("需要先生成 Hummingbot CLI Direct Paper Handoff。")
        install_dir = output_dir / "direct_paper_install"
        output_json = install_dir / "install_report.json"
        output_md = install_dir / "install_report.md"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_cli_direct_paper_install",
            "--handoff-json",
            str(handoff["handoff_json"]),
            "--output-dir",
            str(install_dir),
            "--source-root",
            ".",
            "--session-id",
            str(normalized["session_id"]),
            "--hummingbot-root",
            str(normalized["hummingbot_root"]),
        ]
        if normalized["dry_run"]:
            command.append("--dry-run")
        if normalized["overwrite"]:
            command.append("--overwrite")
        if normalized["clean_event_log"]:
            command.append("--clean-event-log")
        return JobSpec(
            action_id=action_id,
            label="安装 Hummingbot CLI Direct Paper 文件",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "install_report_json": str(output_json),
                "install_report_md": str(output_md),
                "handoff_json": str(handoff["handoff_json"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "handoff_job_id": handoff["job_id"],
            },
        )

    if action_id == "run_hummingbot_paper_session_control":
        install = latest_hummingbot_cli_direct_paper_install(repo_root)
        if not install:
            raise ValueError("需要先安装 Hummingbot CLI Direct Paper 文件。")
        session_dir = output_dir / "paper_session_control"
        output_json = session_dir / "session_control.json"
        output_md = session_dir / "session_control.md"
        state_json = Path("reports/web_reviews/hummingbot_paper_session_state.json")
        return JobSpec(
            action_id=action_id,
            label="Hummingbot Paper Session 控制",
            command=(
                sys.executable,
                "-m",
                "packages.adapters.hummingbot.run_paper_session_control",
                "--install-report-json",
                str(install["install_report_json"]),
                "--output-dir",
                str(session_dir),
                "--state-json",
                str(state_json),
                "--mode",
                str(normalized["mode"]),
                "--session-id",
                str(normalized["session_id"]),
                "--container-name",
                str(normalized["container_name"]),
                "--hummingbot-image",
                str(normalized["hummingbot_image"]),
                "--operator-note",
                str(normalized["operator_note"]),
            ),
            output_dir=absolute_output_dir,
            artifacts={
                "session_control_json": str(output_json),
                "session_control_md": str(output_md),
                "session_state_json": str(state_json),
                "install_report_json": str(install["install_report_json"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "install_job_id": install["job_id"],
            },
        )

    if action_id == "collect_hummingbot_paper_events":
        collection_dir = output_dir / "hummingbot_events"
        output_json = collection_dir / "collection_report.json"
        output_md = collection_dir / "collection_report.md"
        events_jsonl = collection_dir / "events.jsonl"
        state_json = Path("reports/web_reviews/hummingbot_paper_session_state.json")
        return JobSpec(
            action_id=action_id,
            label="采集 Hummingbot Paper Events",
            command=(
                sys.executable,
                "-m",
                "packages.adapters.hummingbot.run_paper_event_collection",
                "--state-json",
                str(state_json),
                "--output-dir",
                str(collection_dir),
                "--source-root",
                ".",
                "--source-path",
                str(normalized["source_path"]),
                "--session-id",
                str(normalized["session_id"]),
                "--max-lines",
                str(normalized["event_collect_max_lines"]),
            ),
            output_dir=absolute_output_dir,
            artifacts={
                "collection_report_json": str(output_json),
                "collection_report_md": str(output_md),
                "events_jsonl": str(events_jsonl),
                "session_state_json": str(state_json),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "run_hummingbot_export_acceptance":
        sandbox = latest_hummingbot_sandbox_prepare(repo_root)
        if not sandbox:
            raise ValueError("需要先生成 Hummingbot Sandbox 准备。")
        prepare_json = str(sandbox.get("sandbox_prepare_json", ""))
        if not prepare_json:
            raise ValueError("Hummingbot Sandbox 准备缺少 prepare report。")
        events_jsonl = str(normalized["events_jsonl"])
        event_collection: dict[str, object] = {}
        if events_jsonl == "auto_latest_collected":
            event_collection = latest_hummingbot_paper_event_collection(repo_root)
            if not event_collection:
                raise ValueError("需要先采集 Hummingbot Paper Events，或手工指定 events_jsonl。")
            events_jsonl = str(event_collection["events_jsonl"])
        output = output_dir / "export_acceptance"
        acceptance_json = output / "acceptance.json"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_sandbox_export_acceptance",
            "--manifest-json",
            str(sandbox["sandbox_manifest_json"]),
            "--prepare-json",
            prepare_json,
            "--events-jsonl",
            events_jsonl,
            "--output-dir",
            str(output),
            "--session-id",
            str(normalized["session_id"]),
            "--event-source",
            str(normalized["event_source"]),
            "--quote-asset",
            str(normalized["quote_asset"]),
        ]
        if normalized["allow_warnings"]:
            command.append("--allow-warnings")
        if normalized["no_require_balance_event"]:
            command.append("--no-require-balance-event")
        if Decimal(str(normalized["starting_quote_balance"])) > Decimal("0"):
            command.extend(["--starting-quote-balance", str(normalized["starting_quote_balance"])])
        return JobSpec(
            action_id=action_id,
            label="运行 Hummingbot Export Acceptance",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "acceptance_json": str(acceptance_json),
                "acceptance_md": str(output / "acceptance.md"),
                "reconciliation_json": str(output / "reconciliation.json"),
                "session_gate_json": str(output / "session_gate.json"),
                "session_package_dir": str(output / "session_package"),
                "events_jsonl": events_jsonl,
                "sandbox_manifest_json": str(sandbox["sandbox_manifest_json"]),
                "sandbox_prepare_json": prepare_json,
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "sandbox_prepare_job_id": sandbox["job_id"],
                "event_collection_job_id": str(event_collection.get("job_id", "")),
                "resolved_events_jsonl": events_jsonl,
            },
        )

    if action_id == "run_hummingbot_observation_review":
        acceptance = latest_hummingbot_export_acceptance(repo_root)
        if not acceptance:
            raise ValueError("需要先运行 Hummingbot Export Acceptance。")
        output_json = output_dir / "hummingbot_observation_review.json"
        output_md = output_dir / "hummingbot_observation_review.md"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_observation_review",
            "--acceptance-json",
            str(acceptance["acceptance_json"]),
            "--events-jsonl",
            str(acceptance["events_jsonl"]),
            "--session-id",
            str(normalized["session_id"]),
            "--target-window-hours",
            str(normalized["target_window_hours"]),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
        if normalized["allow_warnings"]:
            command.append("--allow-warnings")
        return JobSpec(
            action_id=action_id,
            label="生成 Hummingbot Observation Review",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "hummingbot_observation_review_json": str(output_json),
                "hummingbot_observation_review_md": str(output_md),
                "acceptance_json": str(acceptance["acceptance_json"]),
                "events_jsonl": str(acceptance["events_jsonl"]),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "acceptance_job_id": acceptance["job_id"],
            },
        )

    if action_id == "generate_live_execution_package":
        strategy_id = str(normalized["strategy_id"])
        allowed_pairs = _split_scan_roots(str(normalized["allowed_pairs"]))
        if not allowed_pairs:
            raise ValueError("allowed_pairs must contain at least one pair")
        output = output_dir / "live_execution_package"
        package_json = output / "package.json"
        package_md = output / "package.md"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_live_batch_execution_package",
            "--activation-plan-json",
            str(normalized["activation_plan_json"]),
            "--market-data-refresh-json",
            str(normalized["market_data_refresh_json"]),
            "--live-risk-yml",
            str(normalized["live_risk_yml"]),
            "--strategy-dir",
            STRATEGY_OPTIONS[strategy_id],
            "--db",
            str(normalized["db"]),
            "--output-dir",
            str(output),
            "--session-id",
            str(normalized["session_id"]),
        ]
        for pair in allowed_pairs:
            command.extend(["--allowed-pair", pair])
        return JobSpec(
            action_id=action_id,
            label="生成 Live 执行申请包",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "live_execution_package_json": str(package_json),
                "live_execution_package_md": str(package_md),
                "candidate_orders_jsonl": str(output / "candidate_orders.jsonl"),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "allowed_pairs": ",".join(allowed_pairs),
                "live_runner_exposed": False,
                "live_order_submission_armed": False,
            },
        )

    if action_id == "generate_live_post_trade_report":
        output = output_dir / "live_post_trade"
        runner_container = str(normalized["runner_container"])
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_live_post_trade",
            "--event-jsonl",
            str(normalized["event_jsonl"]),
            "--sqlite-db",
            str(normalized["sqlite_db"]),
            "--log-file",
            str(normalized["log_file"]),
            "--candidate-package-json",
            str(normalized["candidate_package_json"]),
            "--runner-package-json",
            str(normalized["runner_package_json"]),
            "--session-id",
            str(normalized["session_id"]),
            "--account-id",
            str(normalized["account_id"]),
            "--strategy-id",
            str(normalized["strategy_id"]),
            "--cad-fx-rate",
            str(normalized["cad_fx_rate"]),
            "--fx-source",
            str(normalized["fx_source"]),
            "--output-dir",
            str(output),
        ]
        if runner_container.lower() != "none":
            command.extend(["--runner-container", runner_container])
        return JobSpec(
            action_id=action_id,
            label="生成 Live Post-trade 复盘",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "post_trade_report_json": str(output / "post_trade_report.json"),
                "post_trade_report_md": str(output / "post_trade_report.md"),
                "daily_report_json": str(output / "daily_report.json"),
                "daily_report_md": str(output / "daily_report.md"),
                "normalized_live_trades_jsonl": str(output / "normalized_live_trades.jsonl"),
                "trade_tax_export_csv": str(output / "trade_tax_export.csv"),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "generate_live_cooldown_review":
        output_json = output_dir / "live_cooldown_review" / "cooldown_review.json"
        output_md = output_dir / "live_cooldown_review" / "cooldown_review.md"
        command = [
            sys.executable,
            "-m",
            "packages.adapters.hummingbot.run_live_cooldown_review",
            "--post-trade-report-json",
            str(normalized["post_trade_report_json"]),
            "--event-jsonl",
            str(normalized["event_jsonl"]),
            "--runner-config-yml",
            str(normalized["runner_config_yml"]),
            "--manual-open-orders-check-json",
            str(normalized["manual_open_orders_check_json"]),
            "--session-id",
            str(normalized["session_id"]),
            "--minimum-cooldown-hours",
            str(normalized["minimum_cooldown_hours"]),
            "--runner-container",
            str(normalized["runner_container"]),
            "--hummingbot-container",
            str(normalized["hummingbot_container"]),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ]
        return JobSpec(
            action_id=action_id,
            label="生成 Live 冷却复盘",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "cooldown_review_json": str(output_json),
                "cooldown_review_md": str(output_md),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "generate_live_initial_closure_report":
        output_json = output_dir / "live_initial_closure" / "initial_closure_report.json"
        output_md = output_dir / "live_initial_closure" / "initial_closure_report.md"
        return JobSpec(
            action_id=action_id,
            label="生成 Live 初始闭环报告",
            command=(
                sys.executable,
                "-m",
                "packages.adapters.hummingbot.run_live_initial_closure",
                "--post-trade-report-json",
                str(normalized["post_trade_report_json"]),
                "--cooldown-review-json",
                str(normalized["cooldown_review_json"]),
                "--session-id",
                str(normalized["session_id"]),
                "--output-json",
                str(output_json),
                "--output-md",
                str(output_md),
            ),
            output_dir=absolute_output_dir,
            artifacts={
                "initial_closure_json": str(output_json),
                "initial_closure_md": str(output_md),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    if action_id == "generate_live_position_exit_plan":
        output = output_dir / "live_position_exit_plan"
        return JobSpec(
            action_id=action_id,
            label="生成 Live 仓位退出计划",
            command=(
                sys.executable,
                "-m",
                "packages.adapters.hummingbot.run_live_position_exit_plan",
                "--initial-closure-json",
                str(normalized["initial_closure_json"]),
                "--output-dir",
                str(output),
                "--session-id",
                str(normalized["session_id"]),
                "--max-exit-notional",
                str(normalized["max_exit_notional"]),
                "--exit-reason",
                str(normalized["exit_reason"]),
            ),
            output_dir=absolute_output_dir,
            artifacts={
                "exit_plan_json": str(output / "exit_plan.json"),
                "exit_plan_md": str(output / "exit_plan.md"),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters={
                **normalized,
                "live_runner_generated": False,
                "live_order_submission_armed": False,
            },
        )

    if action_id == "generate_external_alert_outbox":
        output = output_dir / "external_alert"
        command = [
            sys.executable,
            "-m",
            "packages.observability.run_external_alert_outbox",
            "--output-dir",
            str(output),
            "--channel",
            str(normalized["channel"]),
            "--severity",
            str(normalized["severity"]),
            "--title",
            str(normalized["title"]),
            "--message",
            str(normalized["message"]),
        ]
        if normalized["dispatch_enabled"]:
            command.append("--dispatch-enabled")
        return JobSpec(
            action_id=action_id,
            label="生成外部告警 Outbox",
            command=tuple(command),
            output_dir=absolute_output_dir,
            artifacts={
                "alert_payload_json": str(output / "alert_payload.json"),
                "alert_outbox_jsonl": str(output / "alert_outbox.jsonl"),
                "job_metadata": str(output_dir / JOB_METADATA_FILENAME),
            },
            parameters=normalized,
        )

    raise ValueError(f"unsupported web job action: {action_id}")


def normalize_job_parameters(
    action_id: str,
    parameters: Mapping[str, object] | None = None,
) -> dict[str, object]:
    definitions = ACTION_PARAMETER_DEFINITIONS.get(action_id)
    if definitions is None:
        raise ValueError(f"unsupported web job action: {action_id}")

    supplied = dict(parameters or {})
    allowed = {definition.name for definition in definitions}
    unknown = sorted(set(supplied) - allowed)
    if unknown:
        raise ValueError(f"unsupported parameter(s) for {action_id}: {', '.join(unknown)}")

    values: dict[str, object] = {}
    for definition in definitions:
        raw_value = supplied.get(definition.name, definition.default)
        if definition.input_type == "select":
            values[definition.name] = _normalize_choice(definition, raw_value)
        elif definition.input_type == "date":
            values[definition.name] = _normalize_date(definition, raw_value)
        elif definition.input_type == "number":
            if definition.name in INT_PARAMETER_NAMES:
                values[definition.name] = _normalize_int(definition, raw_value)
            else:
                values[definition.name] = _normalize_decimal(definition, raw_value)
        elif definition.input_type == "checkbox":
            values[definition.name] = _normalize_bool(definition, raw_value)
        elif definition.input_type == "text":
            values[definition.name] = _normalize_text_parameter(definition, raw_value)
        else:  # pragma: no cover - protects future parameter types
            raise ValueError(f"unsupported parameter type: {definition.input_type}")

    if action_id == "run_backtest":
        start = date.fromisoformat(str(values["start"]))
        end = date.fromisoformat(str(values["end"]))
        if start >= end:
            raise ValueError("start must be before end")

    if action_id == "run_parameter_scan":
        values = _apply_scan_template(values)
        _ensure_scan_size(values)

    if action_id in {"run_candidate_walk_forward", "run_candidate_capacity_stress"}:
        start = date.fromisoformat(str(values["start"]))
        end = date.fromisoformat(str(values["end"]))
        if start >= end:
            raise ValueError("start must be before end")

    return values


def serialize_jobs(jobs: tuple[JobRecord, ...]) -> list[dict[str, object]]:
    return [job.to_dict() for job in jobs]


def collect_job_records(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, object]]:
    records = {
        str(job["job_id"]): _with_result_summary(job, repo_root)
        for job in load_persisted_jobs(repo_root)
    }
    for job in serialize_jobs(runtime_jobs):
        records[str(job["job_id"])] = _with_result_summary(job, repo_root)
    return sorted(records.values(), key=lambda job: str(job.get("created_at", "")), reverse=True)


def build_job_queue_state(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    records = collect_job_records(runtime_jobs, repo_root=repo_root)
    status_counts: dict[str, int] = {}
    active_actions: dict[str, str] = {}
    queue_items: list[dict[str, object]] = []

    for record in records:
        status = str(record.get("status", "unknown"))
        action_id = str(record.get("action_id", ""))
        job_id = str(record.get("job_id", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        if status in ACTIVE_JOB_STATUSES and action_id and job_id:
            active_actions[action_id] = job_id
        queue_items.append(
            {
                "job_id": job_id,
                "action_id": action_id,
                "label": str(record.get("label", "")),
                "status": status,
                "created_at": str(record.get("created_at", "")),
                "started_at": record.get("started_at"),
                "completed_at": record.get("completed_at"),
                "output_dir": str(record.get("output_dir", "")),
                "metadata_path": _job_metadata_path(record),
            }
        )

    return {
        "path": str(JOB_QUEUE_STATE_PATH),
        "queue_persistence_enabled": True,
        "last_updated_at": datetime.now(tz=UTC).isoformat(),
        "active_statuses": sorted(ACTIVE_JOB_STATUSES),
        "total_jobs": len(queue_items),
        "status_counts": status_counts,
        "active_actions": active_actions,
        "jobs": queue_items,
    }


def persist_job_queue_state(
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    payload = build_job_queue_state(runtime_jobs, repo_root=repo_root)
    path = repo_root / JOB_QUEUE_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    from apps.web_api.state_db import record_state_document

    record_state_document(
        key="job_queue",
        source_path=str(JOB_QUEUE_STATE_PATH),
        payload=payload,
        repo_root=repo_root,
    )
    return payload


def _job_metadata_path(record: Mapping[str, object]) -> str:
    artifacts = record.get("artifacts")
    if isinstance(artifacts, dict):
        job_metadata = artifacts.get("job_metadata")
        if job_metadata:
            return str(job_metadata)
    output_dir = str(record.get("output_dir", "")).strip()
    return f"{output_dir}/{JOB_METADATA_FILENAME}" if output_dir else ""


def find_job_record(
    job_id: str,
    runtime_jobs: tuple[JobRecord, ...],
    repo_root: Path = REPO_ROOT,
) -> dict[str, object] | None:
    for job in runtime_jobs:
        if job.job_id == job_id:
            return _with_result_summary(job.to_dict(), repo_root)
    for job in load_persisted_jobs(repo_root):
        if str(job.get("job_id", "")) == job_id:
            return _with_result_summary(job, repo_root)
    return None


def load_persisted_jobs(repo_root: Path = REPO_ROOT) -> list[dict[str, object]]:
    jobs_root = repo_root / "reports/web_jobs"
    if not jobs_root.exists():
        return []

    records: list[dict[str, object]] = []
    for metadata_path in jobs_root.glob(f"*/{JOB_METADATA_FILENAME}"):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("job_id") and payload.get("action_id"):
            if str(payload.get("status", "")) in ACTIVE_JOB_STATUSES:
                payload = dict(payload)
                payload["status"] = "interrupted"
                payload["error"] = payload.get("error") or "Job was active when the web API process stopped."
            records.append(payload)
    return records


def _new_job_id(action_id: str) -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{timestamp}_{action_id}_{suffix}"


def _active_job_for_action(jobs, action_id: str) -> JobRecord | None:
    for job in jobs:
        if job.action_id == action_id and job.status in ACTIVE_JOB_STATUSES:
            return job
    return None


def _confirmed_backtest_candidate(repo_root: Path) -> dict[str, str]:
    candidate = read_backtest_candidate(repo_root)
    if candidate is None:
        raise ValueError("confirmed backtest candidate is required before generating paper readiness")
    job_id = str(candidate.get("job_id", "")).strip()
    strategy_id = str(candidate.get("strategy_id", "")).strip()
    artifact_path = str(candidate.get("artifact_path", "")).strip()
    if not job_id or not strategy_id or not artifact_path:
        raise ValueError("confirmed backtest candidate is incomplete")
    candidate_artifact = _safe_artifact_path(repo_root, artifact_path)
    if candidate_artifact is None or not candidate_artifact.exists():
        raise ValueError("confirmed backtest candidate artifact is not available")
    return {
        "job_id": job_id,
        "strategy_id": strategy_id,
        "artifact_path": artifact_path,
    }


def latest_candidate_walk_forward_evidence(
    repo_root: Path,
    candidate: Mapping[str, object],
) -> dict[str, object]:
    candidate_job_id = str(candidate.get("job_id", "")).strip()
    if not candidate_job_id:
        return {}
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "run_candidate_walk_forward":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        parameters = _mapping(job.get("parameters"))
        if str(parameters.get("candidate_job_id", "")) != candidate_job_id:
            continue
        artifacts = _mapping(job.get("artifacts"))
        walk_forward_json = str(artifacts.get("walk_forward_json", ""))
        path = _safe_artifact_path(repo_root, walk_forward_json)
        if path is None or not path.exists():
            continue
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "walk_forward_json": walk_forward_json,
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_candidate_capacity_stress_evidence(
    repo_root: Path,
    candidate: Mapping[str, object],
) -> dict[str, object]:
    candidate_job_id = str(candidate.get("job_id", "")).strip()
    if not candidate_job_id:
        return {}
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "run_candidate_capacity_stress":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        parameters = _mapping(job.get("parameters"))
        if str(parameters.get("candidate_job_id", "")) != candidate_job_id:
            continue
        artifacts = _mapping(job.get("artifacts"))
        capacity_stress_json = str(artifacts.get("capacity_stress_json", ""))
        path = _safe_artifact_path(repo_root, capacity_stress_json)
        if path is None or not path.exists():
            continue
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "capacity_stress_json": capacity_stress_json,
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_passed_paper_readiness(repo_root: Path) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "generate_paper_readiness":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        readiness_json = str(artifacts.get("readiness_json", ""))
        path = _safe_artifact_path(repo_root, readiness_json)
        if path is None or not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status", ""))
        if status not in {"paper_ready", "paper_ready_with_warnings"}:
            continue
        candidate = _mapping(payload.get("candidate_backtest"))
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "readiness_json": readiness_json,
                "status": status,
                "candidate_job_id": str(candidate.get("job_id", "")),
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_paper_smoke_evidence(repo_root: Path) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "run_paper_smoke":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        observation_jsonl = str(artifacts.get("observation_jsonl", ""))
        ledger_jsonl = str(artifacts.get("ledger_jsonl", ""))
        observation_path = _safe_artifact_path(repo_root, observation_jsonl)
        ledger_path = _safe_artifact_path(repo_root, ledger_jsonl)
        if observation_path is None or ledger_path is None:
            continue
        if not observation_path.exists() or not ledger_path.exists():
            continue
        parameters = _mapping(job.get("parameters"))
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "observation_jsonl": observation_jsonl,
                "ledger_jsonl": ledger_jsonl,
                "readiness_json": str(artifacts.get("readiness_json", "")),
                "initial_equity": str(parameters.get("initial_equity", "2000")),
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_paper_observation_review(repo_root: Path) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "generate_paper_observation_review":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        review_json = str(artifacts.get("paper_observation_review_json", ""))
        ledger_jsonl = str(artifacts.get("ledger_jsonl", ""))
        review_path = _safe_artifact_path(repo_root, review_json)
        ledger_path = _safe_artifact_path(repo_root, ledger_jsonl)
        if review_path is None or ledger_path is None:
            continue
        if not review_path.exists() or not ledger_path.exists():
            continue
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "review_json": review_json,
                "ledger_jsonl": ledger_jsonl,
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_hummingbot_sandbox_prepare(repo_root: Path) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "run_hummingbot_sandbox_prepare":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        manifest_json = str(artifacts.get("sandbox_manifest_json", ""))
        manifest_path = _safe_artifact_path(repo_root, manifest_json)
        if manifest_path is None or not manifest_path.exists():
            continue
        prepare_json = str(artifacts.get("sandbox_prepare_json", ""))
        prepare_path = _safe_artifact_path(repo_root, prepare_json) if prepare_json else None
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "sandbox_manifest_json": manifest_json,
                "sandbox_prepare_json": prepare_json if prepare_path is not None and prepare_path.exists() else "",
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_hummingbot_runtime_preflight(repo_root: Path) -> dict[str, object]:
    return _latest_successful_job_artifact(
        repo_root,
        action_id="run_hummingbot_runtime_preflight",
        artifact_key="runtime_preflight_json",
        output_key="runtime_preflight_json",
    )


def latest_hummingbot_cli_direct_paper_handoff(repo_root: Path) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "run_hummingbot_cli_direct_paper_handoff":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        handoff_json = str(artifacts.get("handoff_json", ""))
        script_source = str(artifacts.get("script_source", ""))
        script_config = str(artifacts.get("script_config", ""))
        handoff_path = _safe_artifact_path(repo_root, handoff_json)
        source_path = _safe_artifact_path(repo_root, script_source)
        config_path = _safe_artifact_path(repo_root, script_config)
        if handoff_path is None or source_path is None or config_path is None:
            continue
        if not handoff_path.exists() or not source_path.exists() or not config_path.exists():
            continue
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "handoff_json": handoff_json,
                "script_source": script_source,
                "script_config": script_config,
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_hummingbot_cli_direct_paper_install(repo_root: Path) -> dict[str, object]:
    return _latest_successful_job_artifact(
        repo_root,
        action_id="install_hummingbot_cli_direct_paper_files",
        artifact_key="install_report_json",
        output_key="install_report_json",
    )


def latest_hummingbot_paper_event_collection(repo_root: Path) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "collect_hummingbot_paper_events":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        report_json = str(artifacts.get("collection_report_json", ""))
        events_jsonl = str(artifacts.get("events_jsonl", ""))
        report_path = _safe_artifact_path(repo_root, report_json)
        events_path = _safe_artifact_path(repo_root, events_jsonl)
        if report_path is None or events_path is None:
            continue
        if not report_path.exists() or not events_path.exists():
            continue
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "collection_report_json": report_json,
                "events_jsonl": events_jsonl,
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def latest_hummingbot_export_acceptance(repo_root: Path) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != "run_hummingbot_export_acceptance":
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        acceptance_json = str(artifacts.get("acceptance_json", ""))
        events_jsonl = str(artifacts.get("events_jsonl", ""))
        acceptance_path = _safe_artifact_path(repo_root, acceptance_json)
        events_path = _input_path(repo_root, events_jsonl)
        if acceptance_path is None:
            continue
        if not acceptance_path.exists() or not events_path.exists():
            continue
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                "acceptance_json": acceptance_json,
                "events_jsonl": events_jsonl,
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def _latest_successful_job_artifact(
    repo_root: Path,
    *,
    action_id: str,
    artifact_key: str,
    output_key: str,
) -> dict[str, object]:
    matches: list[dict[str, object]] = []
    for job in load_persisted_jobs(repo_root):
        if str(job.get("action_id", "")) != action_id:
            continue
        if str(job.get("status", "")) != "succeeded":
            continue
        artifacts = _mapping(job.get("artifacts"))
        artifact_path = str(artifacts.get(artifact_key, ""))
        path = _safe_artifact_path(repo_root, artifact_path)
        if path is None or not path.exists():
            continue
        matches.append(
            {
                "job_id": str(job.get("job_id", "")),
                "created_at": str(job.get("created_at", "")),
                output_key: artifact_path,
            }
        )
    return sorted(matches, key=lambda item: str(item.get("created_at", "")), reverse=True)[0] if matches else {}


def _ensure_readiness_evidence_exists(repo_root: Path, path: Path, label: str) -> None:
    absolute = _safe_artifact_path(repo_root, str(path))
    if absolute is None or not absolute.exists():
        raise ValueError(f"{label} evidence is not available: {path}")


def _ensure_readiness_disposition_allows_rerun(repo_root: Path, candidate: Mapping[str, object]) -> None:
    recorded = read_recorded_disposition(repo_root)
    resolution = disposition_resolution(recorded, candidate)
    if resolution.get("resolution_status") == "requires_new_candidate":
        raise ValueError(str(resolution.get("message", "select a new candidate before generating paper readiness")))


def _load_candidate_backtest(repo_root: Path, candidate: Mapping[str, object]) -> dict[str, object]:
    artifact_path = str(candidate.get("artifact_path", ""))
    path = _safe_artifact_path(repo_root, artifact_path)
    if path is None or not path.exists():
        raise ValueError("confirmed backtest candidate artifact is not available")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("confirmed backtest candidate artifact is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("confirmed backtest candidate artifact is invalid")
    return payload


def _append_candidate_walk_forward_grid(
    command: list[str],
    strategy_id: str,
    parameters: Mapping[str, object],
) -> None:
    fee_rate = _required_candidate_parameter(parameters, "fee_rate")
    slippage_bps = _required_candidate_parameter(parameters, "slippage_bps")
    command.extend(["--fee-rates", fee_rate, "--slippage-bps", slippage_bps])
    if strategy_id == "crypto_relative_strength_v1":
        command.extend(
            [
                "--lookback-windows",
                _required_candidate_parameter(parameters, "lookback_window"),
                "--rotation-top-n-values",
                _required_candidate_parameter(parameters, "top_n"),
                "--min-momentum",
                _optional_candidate_parameter(parameters, "min_momentum", default="0"),
            ]
        )
        return
    command.extend(
        [
            "--fast-windows",
            _required_candidate_parameter(parameters, "fast_window"),
            "--slow-windows",
            _required_candidate_parameter(parameters, "slow_window"),
            "--min-trend-strengths",
            _optional_candidate_parameter(parameters, "min_trend_strength", default="0"),
            "--max-volatility",
            _optional_candidate_parameter(parameters, "max_volatility", default="none"),
        ]
    )


def _required_candidate_parameter(parameters: Mapping[str, object], key: str) -> str:
    value = _optional_candidate_parameter(parameters, key, default="")
    if not value:
        raise ValueError(f"candidate backtest parameter is required for walk-forward: {key}")
    return value


def _optional_candidate_parameter(parameters: Mapping[str, object], key: str, *, default: str) -> str:
    value = parameters.get(key)
    text = "" if value is None else str(value).strip()
    if text.lower() in {"", "none", "null"}:
        return default
    return text


def _scan_recommendation(repo_root: Path, *, scan_job_id: str, run_id: str) -> dict[str, object]:
    metadata_path = _safe_artifact_path(repo_root, f"reports/web_jobs/{scan_job_id}/{JOB_METADATA_FILENAME}")
    if metadata_path is None or not metadata_path.exists():
        raise ValueError("parameter scan job metadata is not available")
    try:
        job = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("parameter scan job metadata is invalid") from exc
    if not isinstance(job, dict):
        raise ValueError("parameter scan job metadata is invalid")
    if str(job.get("action_id", "")) != "run_parameter_scan":
        raise ValueError("recommended backtest source must be a parameter scan job")
    if str(job.get("status", "")) != "succeeded":
        raise ValueError("parameter scan job must be succeeded before running a recommendation")

    artifacts = _mapping(job.get("artifacts"))
    scan = _load_json_artifact(repo_root, artifacts, "parameter_scan_json")
    if scan is None:
        raise ValueError("parameter scan artifact is not available")
    runs = scan.get("runs")
    if not isinstance(runs, list):
        raise ValueError("parameter scan artifact has no runs")
    for raw_run in runs:
        run = _mapping(raw_run)
        if str(run.get("run_id", "")) != run_id:
            continue
        return {
            "scan_job_id": scan_job_id,
            "run_id": run_id,
            "rank": run.get("rank"),
            "strategy_id": str(scan.get("strategy_id", "")),
            "artifact_path": str(artifacts.get("parameter_scan_json", "")),
            "parameters": _string_mapping(_mapping(run.get("parameters"))),
            "metrics": _string_mapping(_mapping(run.get("metrics"))),
        }
    raise ValueError("parameter scan run was not found")


def _append_recommended_backtest_overrides(command: list[str], parameters: Mapping[str, object]) -> None:
    pairs = (
        ("fee_rate", "--fee-rate"),
        ("slippage_bps", "--slippage-bps"),
        ("fast_window", "--fast-window"),
        ("slow_window", "--slow-window"),
        ("lookback_window", "--lookback-window"),
        ("top_n", "--top-n"),
        ("min_momentum", "--min-momentum"),
        ("min_trend_strength", "--min-trend-strength"),
        ("max_volatility", "--max-volatility"),
    )
    for key, flag in pairs:
        value = parameters.get(key)
        if value is None or str(value) == "":
            continue
        if key in {"fast_window", "slow_window", "lookback_window", "top_n"} and str(value) == "0":
            continue
        command.extend([flag, str(value)])


def _split_scan_roots(value: str) -> list[str]:
    roots = [item.strip() for item in re.split(r"[\n,]+", value) if item.strip()]
    if any(Path(root).is_absolute() and ".." in Path(root).parts for root in roots):
        raise ValueError("scan_roots contains an invalid path")
    return roots


def _write_job_metadata(record: JobRecord) -> None:
    metadata_path = record.output_dir / JOB_METADATA_FILENAME
    payload = _with_result_summary(record.to_dict(), record.cwd)
    metadata_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _with_result_summary(job: Mapping[str, object], repo_root: Path) -> dict[str, object]:
    payload = dict(job)
    payload["result_summary"] = _result_summary(payload, repo_root)
    return payload


def _result_summary(job: Mapping[str, object], repo_root: Path) -> dict[str, object] | None:
    action_id = str(job.get("action_id", ""))
    artifacts = job.get("artifacts")
    if not isinstance(artifacts, dict):
        return None

    if action_id in BACKTEST_JOB_ACTION_IDS:
        data = _load_json_artifact(repo_root, artifacts, "backtest_json")
        return _backtest_summary(data) if data else None

    if action_id == "refresh_market_data":
        data = _load_json_artifact(repo_root, artifacts, "market_data_refresh_json")
        return _market_data_refresh_summary(data) if data else None

    if action_id == "query_strategy_data_quality":
        data = _load_json_artifact(repo_root, artifacts, "strategy_data_quality_json")
        return _strategy_data_quality_summary(data) if data else None

    if action_id == "run_parameter_scan":
        data = _load_json_artifact(repo_root, artifacts, "parameter_scan_json")
        return _parameter_scan_summary(data) if data else None

    if action_id == "run_candidate_walk_forward":
        data = _load_json_artifact(repo_root, artifacts, "walk_forward_json")
        return _walk_forward_summary(data) if data else None

    if action_id == "run_candidate_capacity_stress":
        data = _load_json_artifact(repo_root, artifacts, "capacity_stress_json")
        return _backtest_summary(data) if data else None

    if action_id == "generate_paper_readiness":
        data = _load_json_artifact(repo_root, artifacts, "readiness_json")
        return _paper_readiness_summary(data) if data else None

    if action_id == "run_paper_smoke":
        data = _load_json_artifact(repo_root, artifacts, "summary_json")
        return _paper_smoke_summary(data) if data else None

    if action_id == "generate_paper_observation_review":
        data = _load_json_artifact(repo_root, artifacts, "paper_observation_review_json")
        return _paper_observation_review_summary(data) if data else None

    if action_id == "run_hummingbot_sandbox_prepare":
        data = _load_json_artifact(repo_root, artifacts, "sandbox_prepare_json")
        return _hummingbot_sandbox_prepare_summary(data) if data else None

    if action_id == "run_hummingbot_runtime_preflight":
        data = _load_json_artifact(repo_root, artifacts, "runtime_preflight_json")
        return _hummingbot_runtime_preflight_summary(data) if data else None

    if action_id == "run_hummingbot_cli_direct_paper_handoff":
        data = _load_json_artifact(repo_root, artifacts, "handoff_json")
        return _hummingbot_cli_direct_handoff_summary(data) if data else None

    if action_id == "install_hummingbot_cli_direct_paper_files":
        data = _load_json_artifact(repo_root, artifacts, "install_report_json")
        return _hummingbot_cli_direct_install_summary(data) if data else None

    if action_id == "run_hummingbot_paper_session_control":
        data = _load_json_artifact(repo_root, artifacts, "session_control_json")
        return _hummingbot_paper_session_control_summary(data) if data else None

    if action_id == "collect_hummingbot_paper_events":
        data = _load_json_artifact(repo_root, artifacts, "collection_report_json")
        return _hummingbot_paper_event_collection_summary(data) if data else None

    if action_id == "run_hummingbot_export_acceptance":
        data = _load_json_artifact(repo_root, artifacts, "acceptance_json")
        return _hummingbot_export_acceptance_summary(data) if data else None

    if action_id == "run_hummingbot_observation_review":
        data = _load_json_artifact(repo_root, artifacts, "hummingbot_observation_review_json")
        return _hummingbot_observation_review_summary(data) if data else None

    if action_id == "generate_live_execution_package":
        data = _load_json_artifact(repo_root, artifacts, "live_execution_package_json")
        return _live_execution_package_summary(data) if data else None

    if action_id == "generate_live_post_trade_report":
        data = _load_json_artifact(repo_root, artifacts, "post_trade_report_json")
        return _live_post_trade_summary(data) if data else None

    if action_id == "generate_live_cooldown_review":
        data = _load_json_artifact(repo_root, artifacts, "cooldown_review_json")
        return _live_cooldown_summary(data) if data else None

    if action_id == "generate_live_initial_closure_report":
        data = _load_json_artifact(repo_root, artifacts, "initial_closure_json")
        return _live_initial_closure_summary(data) if data else None

    if action_id == "generate_live_position_exit_plan":
        data = _load_json_artifact(repo_root, artifacts, "exit_plan_json")
        return _live_position_exit_summary(data) if data else None

    if action_id == "generate_external_alert_outbox":
        data = _load_json_artifact(repo_root, artifacts, "alert_payload_json")
        return _external_alert_outbox_summary(data) if data else None

    return None


def _backtest_summary(data: Mapping[str, object]) -> dict[str, object]:
    metrics = _mapping(data.get("metrics"))
    parameters = _mapping(data.get("parameters"))
    return {
        "kind": "backtest",
        "title": "回测摘要",
        "metrics": [
            _metric("strategy", data.get("strategy_id")),
            _metric("start", parameters.get("start")),
            _metric("end", parameters.get("end")),
            _metric("total_return", metrics.get("total_return")),
            _metric("max_drawdown", metrics.get("max_drawdown")),
            _metric("tail_loss", metrics.get("tail_loss")),
            _metric("turnover", metrics.get("turnover")),
            _metric("trade_count", metrics.get("trade_count")),
            _metric("end_equity", metrics.get("end_equity")),
        ],
    }


def _market_data_refresh_summary(data: Mapping[str, object]) -> dict[str, object]:
    results = data.get("results")
    result_items = results if isinstance(results, list) else []
    statuses = [str(_mapping(item).get("status", "")) for item in result_items]
    total_fetched = sum(_intish(_mapping(item).get("fetched_candles")) for item in result_items)
    total_stored = sum(_intish(_mapping(item).get("stored_candles")) for item in result_items)
    return {
        "kind": "market_data_refresh",
        "title": "公开行情刷新摘要",
        "metrics": [
            _metric("strategy", data.get("strategy_id")),
            _metric("status", data.get("status")),
            _metric("exchange", data.get("exchange")),
            _metric("interval", data.get("interval")),
            _metric("pairs", len(result_items)),
            _metric("ok", statuses.count("ok")),
            _metric("up_to_date", statuses.count("up_to_date")),
            _metric("failed", statuses.count("failed")),
            _metric("fetched", total_fetched),
            _metric("stored", total_stored),
        ],
    }


def _strategy_data_quality_summary(data: Mapping[str, object]) -> dict[str, object]:
    results = data.get("results")
    result_items = results if isinstance(results, list) else []
    complete = sum(1 for item in result_items if _mapping(item).get("complete") is True)
    quality_ok = sum(1 for item in result_items if _mapping(item).get("quality_ok") is True)
    candles = sum(_intish(_mapping(item).get("candles")) for item in result_items)
    expected = sum(_intish(_mapping(item).get("expected")) for item in result_items)
    missing = max(expected - candles, 0)
    return {
        "kind": "strategy_data_quality",
        "title": "策略数据质量摘要",
        "metrics": [
            _metric("strategy", data.get("strategy_id")),
            _metric("queries", len(result_items)),
            _metric("complete", complete),
            _metric("quality_ok", quality_ok),
            _metric("candles", candles),
            _metric("expected", expected),
            _metric("missing", missing),
        ],
    }


def _parameter_scan_summary(data: Mapping[str, object]) -> dict[str, object]:
    best_run = _mapping(data.get("best_run"))
    metrics = _mapping(best_run.get("metrics"))
    runs = data.get("runs")
    run_count = len(runs) if isinstance(runs, list) else 0
    return {
        "kind": "parameter_scan",
        "title": "参数扫描摘要",
        "metrics": [
            _metric("strategy", data.get("strategy_id")),
            _metric("runs", run_count),
            _metric("best_rank", best_run.get("rank")),
            _metric("best_run", best_run.get("run_id")),
            _metric("total_return", metrics.get("total_return")),
            _metric("max_drawdown", metrics.get("max_drawdown")),
            _metric("tail_loss", metrics.get("tail_loss")),
            _metric("turnover", metrics.get("turnover")),
            _metric("trade_count", metrics.get("trade_count")),
        ],
    }


def _walk_forward_summary(data: Mapping[str, object]) -> dict[str, object]:
    summary = _mapping(data.get("summary"))
    return {
        "kind": "walk_forward",
        "title": "Walk-forward 摘要",
        "metrics": [
            _metric("strategy", data.get("strategy_id")),
            _metric("folds", summary.get("folds")),
            _metric("positive_folds", summary.get("selected_positive_folds")),
            _metric("median_return", summary.get("median_selected_test_return")),
            _metric("worst_return", summary.get("worst_selected_test_return")),
            _metric("worst_drawdown", summary.get("worst_selected_test_drawdown")),
            _metric("worst_tail_loss", summary.get("worst_selected_test_tail_loss")),
        ],
    }


def _paper_readiness_summary(data: Mapping[str, object]) -> dict[str, object]:
    alerts = data.get("alerts")
    alert_items = alerts if isinstance(alerts, list) else []
    critical_alerts = [
        alert for alert in alert_items if str(_mapping(alert).get("severity", "")).upper() == "CRITICAL"
    ]
    warning_alerts = [
        alert for alert in alert_items if str(_mapping(alert).get("severity", "")).upper() == "WARN"
    ]
    summary = _mapping(data.get("summary"))
    capacity = _mapping(data.get("capacity"))
    candidate = _mapping(data.get("candidate_backtest"))
    return {
        "kind": "paper_readiness",
        "title": "Paper 准入摘要",
        "metrics": [
            _metric("strategy", data.get("strategy_id")),
            _metric("status", data.get("status")),
            _metric("candidate_job", candidate.get("job_id")),
            _metric("candidate_strategy", candidate.get("strategy_id")),
            _metric("alerts", len(alert_items)),
            _metric("critical_alerts", len(critical_alerts)),
            _metric("warning_alerts", len(warning_alerts)),
            _metric("median_return", summary.get("median_return")),
            _metric("worst_drawdown", summary.get("worst_drawdown")),
            _metric("capacity_equity", capacity.get("estimated_capacity_equity")),
        ],
    }


def _paper_smoke_summary(data: Mapping[str, object]) -> dict[str, object]:
    return {
        "kind": "paper_smoke",
        "title": "Paper Smoke 摘要",
        "metrics": [
            _metric("status", data.get("status")),
            _metric("cycles", data.get("cycles")),
            _metric("ok_cycles", data.get("ok_cycles")),
            _metric("failed_cycles", data.get("failed_cycles")),
            _metric("routed_orders", data.get("routed_orders")),
            _metric("approved_orders", data.get("approved_orders")),
            _metric("rejected_orders", data.get("rejected_orders")),
            _metric("last_equity", data.get("last_equity")),
            _metric("max_drawdown", data.get("max_drawdown")),
        ],
    }


def _paper_observation_review_summary(data: Mapping[str, object]) -> dict[str, object]:
    observation = _mapping(data.get("observation"))
    trading = _mapping(data.get("trading"))
    market_data = _mapping(data.get("market_data"))
    alerts = data.get("alerts")
    alert_count = len(alerts) if isinstance(alerts, list) else 0
    return {
        "kind": "paper_observation_review",
        "title": "Paper 观察复盘摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("strategy", data.get("strategy_id")),
            _metric("cycles", observation.get("cycles")),
            _metric("ok_cycle_ratio", observation.get("ok_cycle_ratio")),
            _metric("net_return", trading.get("net_return")),
            _metric("max_drawdown", trading.get("max_drawdown")),
            _metric("rejected_orders", trading.get("rejected_orders")),
            _metric("incomplete_cycles", market_data.get("incomplete_cycles")),
            _metric("alerts", alert_count),
        ],
    }


def _hummingbot_sandbox_prepare_summary(data: Mapping[str, object]) -> dict[str, object]:
    manifest = _mapping(data.get("manifest"))
    lifecycle = _mapping(data.get("lifecycle"))
    checks = _mapping(lifecycle.get("checks"))
    orders = manifest.get("orders")
    alerts = data.get("alerts")
    return {
        "kind": "hummingbot_sandbox_prepare",
        "title": "Hummingbot Sandbox 准备摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("connector", manifest.get("connector_name")),
            _metric("controller", manifest.get("controller_name")),
            _metric("orders", len(orders) if isinstance(orders, list) else 0),
            _metric("total_notional", manifest.get("total_notional")),
            _metric("submitted_orders", checks.get("submitted_orders")),
            _metric("terminal_orders", checks.get("terminal_orders")),
            _metric("duplicate_client_ids", checks.get("duplicate_client_ids")),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _hummingbot_runtime_preflight_summary(data: Mapping[str, object]) -> dict[str, object]:
    connectors = data.get("connector_configs")
    paper_connectors = data.get("paper_trade_connectors")
    alerts = data.get("alerts")
    return {
        "kind": "hummingbot_runtime_preflight",
        "title": "Hummingbot Runtime Preflight 摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("session", data.get("session_id")),
            _metric("expected_connector", data.get("expected_connector")),
            _metric("connector_configs", len(connectors) if isinstance(connectors, list) else 0),
            _metric("paper_connectors", len(paper_connectors) if isinstance(paper_connectors, list) else 0),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _hummingbot_cli_direct_handoff_summary(data: Mapping[str, object]) -> dict[str, object]:
    summary = _mapping(data.get("summary"))
    alerts = data.get("alerts")
    return {
        "kind": "hummingbot_cli_direct_paper_handoff",
        "title": "Hummingbot CLI Direct Paper Handoff 摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("session", data.get("session_id")),
            _metric("script_config", data.get("script_config_name")),
            _metric("orders", summary.get("order_count")),
            _metric("connector", summary.get("connector_name")),
            _metric("runtime_preflight", summary.get("runtime_preflight_decision")),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _hummingbot_cli_direct_install_summary(data: Mapping[str, object]) -> dict[str, object]:
    summary = _mapping(data.get("summary"))
    alerts = data.get("alerts")
    return {
        "kind": "hummingbot_cli_direct_paper_install",
        "title": "Hummingbot CLI Direct Paper 文件安装摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("session", data.get("session_id")),
            _metric("hummingbot_root", data.get("hummingbot_root")),
            _metric("dry_run", data.get("dry_run")),
            _metric("installed", summary.get("installed")),
            _metric("unchanged", summary.get("unchanged")),
            _metric("planned", summary.get("planned")),
            _metric("blocked", summary.get("blocked")),
            _metric("event_log_status", summary.get("event_log_status")),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _hummingbot_paper_session_control_summary(data: Mapping[str, object]) -> dict[str, object]:
    alerts = data.get("alerts")
    state = _mapping(data.get("state"))
    return {
        "kind": "hummingbot_paper_session_control",
        "title": "Hummingbot Paper Session 控制摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("mode", data.get("mode")),
            _metric("session", data.get("session_id")),
            _metric("state", state.get("status")),
            _metric("container", data.get("container_name")),
            _metric("script_config", data.get("script_config_name")),
            _metric("event_log", data.get("event_log_host_path")),
            _metric("process_started_by_web", data.get("process_started_by_web")),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _hummingbot_paper_event_collection_summary(data: Mapping[str, object]) -> dict[str, object]:
    alerts = data.get("alerts")
    summary = _mapping(data.get("summary"))
    return {
        "kind": "hummingbot_paper_event_collection",
        "title": "Hummingbot Paper Event 采集摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("session", data.get("session_id")),
            _metric("events", summary.get("event_count")),
            _metric("parse_errors", summary.get("parse_errors")),
            _metric("truncated", summary.get("truncated")),
            _metric("first_event", summary.get("first_event_type")),
            _metric("last_event", summary.get("last_event_type")),
            _metric("last_timestamp", summary.get("last_timestamp")),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _hummingbot_export_acceptance_summary(data: Mapping[str, object]) -> dict[str, object]:
    reconciliation = _mapping(data.get("reconciliation_summary"))
    session_gate = _mapping(data.get("session_gate_summary"))
    package = _mapping(data.get("package_summary"))
    alerts = data.get("alerts")
    return {
        "kind": "hummingbot_export_acceptance",
        "title": "Hummingbot Export Acceptance 摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("session", data.get("session_id")),
            _metric("event_source", data.get("event_source")),
            _metric("events", reconciliation.get("event_count")),
            _metric("submitted_orders", reconciliation.get("submitted_orders")),
            _metric("terminal_orders", reconciliation.get("terminal_orders")),
            _metric("session_gate", session_gate.get("decision")),
            _metric("package", package.get("decision")),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _hummingbot_observation_review_summary(data: Mapping[str, object]) -> dict[str, object]:
    event_window = _mapping(data.get("event_window"))
    alerts = data.get("alerts")
    return {
        "kind": "hummingbot_observation_review",
        "title": "Hummingbot Observation Review 摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("session", data.get("session_id")),
            _metric("target_hours", event_window.get("target_window_hours")),
            _metric("events", event_window.get("event_count")),
            _metric("event_source", event_window.get("event_source")),
            _metric("alerts", len(alerts) if isinstance(alerts, list) else 0),
        ],
    }


def _live_execution_package_summary(data: Mapping[str, object]) -> dict[str, object]:
    orders = data.get("candidate_orders")
    risk = _mapping(data.get("risk_summary"))
    return {
        "kind": "live_execution_package",
        "title": "Live 执行申请包摘要",
        "metrics": [
            _metric("decision", data.get("decision")),
            _metric("session", data.get("session_id")),
            _metric("strategy", data.get("strategy_id")),
            _metric("batch", data.get("batch_id")),
            _metric("connector", data.get("connector")),
            _metric("orders", len(orders) if isinstance(orders, list) else 0),
            _metric("max_batch_notional", risk.get("max_batch_notional")),
            _metric("max_order_notional", risk.get("max_order_notional")),
            _metric("runner_generated", data.get("execution_runner_generated")),
            _metric("live_order_armed", data.get("live_order_submission_armed")),
        ],
    }


def _live_post_trade_summary(data: Mapping[str, object]) -> dict[str, object]:
    order_checks = _mapping(data.get("order_checks"))
    fill_summary = _mapping(data.get("fill_summary"))
    return {
        "kind": "live_post_trade",
        "title": "Live Post-trade 复盘摘要",
        "metrics": [
            _metric("status", data.get("status")),
            _metric("strategy", data.get("strategy_id")),
            _metric("account", data.get("account_id")),
            _metric("submitted", order_checks.get("submitted_orders")),
            _metric("filled", order_checks.get("filled_orders")),
            _metric("db_fills", order_checks.get("db_fills")),
            _metric("gross_quote", fill_summary.get("gross_quote_notional")),
            _metric("net_base", fill_summary.get("net_base_quantity")),
        ],
    }


def _live_cooldown_summary(data: Mapping[str, object]) -> dict[str, object]:
    window = _mapping(data.get("cooldown_window"))
    manual = _mapping(data.get("manual_checks"))
    return {
        "kind": "live_cooldown",
        "title": "Live 冷却复盘摘要",
        "metrics": [
            _metric("status", data.get("status")),
            _metric("cooldown_elapsed", window.get("cooldown_elapsed")),
            _metric("elapsed_hours", window.get("elapsed_hours")),
            _metric("next_review", window.get("next_review_not_before")),
            _metric("open_orders", manual.get("open_orders_check_status")),
        ],
    }


def _live_initial_closure_summary(data: Mapping[str, object]) -> dict[str, object]:
    next_decision = _mapping(data.get("next_live_decision"))
    position = _mapping(data.get("position_lifecycle_plan"))
    closure = _mapping(data.get("closure_summary"))
    return {
        "kind": "live_initial_closure",
        "title": "Live 初始闭环摘要",
        "metrics": [
            _metric("status", data.get("status")),
            _metric("closed", closure.get("initial_flow_closed")),
            _metric("next_live", next_decision.get("decision")),
            _metric("stance", position.get("stance")),
            _metric("exit_requires_activation", position.get("exit_requires_activation")),
        ],
    }


def _live_position_exit_summary(data: Mapping[str, object]) -> dict[str, object]:
    return {
        "kind": "live_position_exit_plan",
        "title": "Live 仓位退出计划摘要",
        "metrics": [
            _metric("status", data.get("status")),
            _metric("session", data.get("session_id")),
            _metric("pair", data.get("trading_pair")),
            _metric("side", data.get("side")),
            _metric("quantity", data.get("quantity")),
            _metric("max_exit_notional", data.get("max_exit_notional")),
            _metric("runner_generated", data.get("live_runner_generated")),
            _metric("live_order_armed", data.get("live_order_submission_armed")),
        ],
    }


def _external_alert_outbox_summary(data: Mapping[str, object]) -> dict[str, object]:
    return {
        "kind": "external_alert_outbox",
        "title": "外部告警 Outbox 摘要",
        "metrics": [
            _metric("status", data.get("status")),
            _metric("channel", data.get("channel")),
            _metric("severity", data.get("severity")),
            _metric("title", data.get("title")),
            _metric("dispatch_enabled", data.get("dispatch_enabled")),
        ],
    }


def _load_json_artifact(repo_root: Path, artifacts: Mapping[object, object], key: str) -> dict[str, object] | None:
    value = artifacts.get(key)
    if not isinstance(value, str):
        return None
    path = _safe_artifact_path(repo_root, value)
    if path is None or not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _safe_artifact_path(repo_root: Path, relative_path: str) -> Path | None:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    absolute = (repo_root / path).resolve()
    try:
        absolute.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return absolute


def _input_path(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (repo_root / path)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _string_mapping(value: Mapping[str, object]) -> dict[str, str]:
    return {str(key): "" if item is None else str(item) for key, item in value.items()}


def _metric(label: str, value: object) -> dict[str, str]:
    return {"label": label, "value": "" if value is None else str(value)}


def _intish(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _normalize_choice(definition: JobParameterSpec, value: object) -> str:
    text = str(value).strip()
    allowed = {option_value for _, option_value in definition.options}
    if text not in allowed:
        raise ValueError(f"{definition.name} must be one of: {', '.join(sorted(allowed))}")
    return text


def _normalize_date(definition: JobParameterSpec, value: object) -> str:
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as exc:
        raise ValueError(f"{definition.name} must use YYYY-MM-DD") from exc


def _normalize_decimal(definition: JobParameterSpec, value: object) -> str:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"{definition.name} must be a decimal number") from exc
    if not number.is_finite():
        raise ValueError(f"{definition.name} must be finite")
    if definition.min_value is not None and number < Decimal(definition.min_value):
        raise ValueError(f"{definition.name} must be >= {definition.min_value}")
    if definition.max_value is not None and number > Decimal(definition.max_value):
        raise ValueError(f"{definition.name} must be <= {definition.max_value}")
    return format(number, "f")


def _normalize_int(definition: JobParameterSpec, value: object) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{definition.name} must be an integer")
    try:
        number = int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{definition.name} must be an integer") from exc
    if definition.min_value is not None and number < int(definition.min_value):
        raise ValueError(f"{definition.name} must be >= {definition.min_value}")
    if definition.max_value is not None and number > int(definition.max_value):
        raise ValueError(f"{definition.name} must be <= {definition.max_value}")
    return number


def _normalize_bool(definition: JobParameterSpec, value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{definition.name} must be a boolean")


def _normalize_text_parameter(definition: JobParameterSpec, value: object) -> str:
    if definition.name == "account_id":
        return _normalize_account_id(definition, value)
    if definition.name in CSV_INT_PARAMETERS:
        return _normalize_csv_ints(definition, value)
    if definition.name in CSV_DECIMAL_PARAMETERS:
        return _normalize_csv_decimals(definition, value)
    if definition.name in CSV_OPTIONAL_DECIMAL_PARAMETERS:
        return _normalize_csv_optional_decimals(definition, value)
    if definition.name == "scan_job_id":
        return _normalize_scan_job_id(definition, value)
    if definition.name == "run_id":
        return _normalize_scan_run_id(definition, value)
    text = str(value).strip()
    if not text:
        raise ValueError(f"{definition.name} is required")
    return text


def _normalize_account_id(definition: JobParameterSpec, value: object) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}", text):
        raise ValueError(f"{definition.name} must be 3-64 chars: letters, digits, dot, underscore or dash")
    return text


def _normalize_csv_ints(definition: JobParameterSpec, value: object) -> str:
    items = [item.strip() for item in str(value).split(",") if item.strip()]
    if not items:
        raise ValueError(f"{definition.name} must contain at least one integer")
    parsed: list[str] = []
    for item in items:
        try:
            number = int(item)
        except ValueError as exc:
            raise ValueError(f"{definition.name} must contain integers") from exc
        if number <= 0:
            raise ValueError(f"{definition.name} values must be positive")
        parsed.append(str(number))
    return ",".join(parsed)


def _normalize_csv_decimals(definition: JobParameterSpec, value: object) -> str:
    items = [item.strip() for item in str(value).split(",") if item.strip()]
    if not items:
        raise ValueError(f"{definition.name} must contain at least one decimal")
    return ",".join(_normalize_decimal_item(definition, item) for item in items)


def _normalize_csv_optional_decimals(definition: JobParameterSpec, value: object) -> str:
    items = [item.strip() for item in str(value).split(",") if item.strip()]
    if not items:
        raise ValueError(f"{definition.name} must contain at least one decimal or none")
    normalized: list[str] = []
    for item in items:
        lowered = item.lower()
        if lowered in {"none", "null", "off"}:
            normalized.append("none")
        else:
            normalized.append(_normalize_decimal_item(definition, item))
    return ",".join(normalized)


def _normalize_decimal_item(definition: JobParameterSpec, value: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{definition.name} must contain decimal numbers") from exc
    if not number.is_finite():
        raise ValueError(f"{definition.name} values must be finite")
    return format(number, "f")


def _normalize_scan_job_id(definition: JobParameterSpec, value: object) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}", text):
        raise ValueError(f"{definition.name} is invalid")
    return text


def _normalize_scan_run_id(definition: JobParameterSpec, value: object) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,191}", text):
        raise ValueError(f"{definition.name} is invalid")
    return text


def _ensure_scan_size(values: Mapping[str, object]) -> None:
    strategy_id = str(values["strategy_id"])
    if strategy_id == "crypto_relative_strength_v1":
        count = (
            _csv_count(str(values["lookback_windows"]))
            * _csv_count(str(values["rotation_top_n_values"]))
            * _csv_count(str(values["min_momentum"]))
        )
    else:
        count = (
            _valid_window_pair_count(str(values["fast_windows"]), str(values["slow_windows"]))
            * _csv_count(str(values["min_trend_strengths"]))
            * _csv_count(str(values["max_volatility"]))
        )
    if count <= 0:
        raise ValueError("parameter scan must produce at least one valid run")
    if count > 100:
        raise ValueError("parameter scan is limited to 100 runs in the web console")


def _apply_scan_template(values: dict[str, object]) -> dict[str, object]:
    template_id = str(values.get("scan_template", "custom"))
    if template_id == "custom":
        return values
    strategy_id = str(values["strategy_id"])
    strategy_templates = SCAN_TEMPLATES.get(strategy_id, {})
    template = strategy_templates.get(template_id)
    if template is None:
        raise ValueError(f"unsupported scan template for {strategy_id}: {template_id}")
    merged = dict(values)
    for key, value in template.items():
        merged[key] = value
    return merged


def _csv_count(value: str) -> int:
    return len([item for item in value.split(",") if item.strip()])


def _valid_window_pair_count(fast_windows: str, slow_windows: str) -> int:
    fast = [int(item) for item in fast_windows.split(",") if item.strip()]
    slow = [int(item) for item in slow_windows.split(",") if item.strip()]
    return sum(1 for fast_window in fast for slow_window in slow if fast_window < slow_window)


def _safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")[:120] or "recommendation"
