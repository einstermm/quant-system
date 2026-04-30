"""FastAPI entry point for the web dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi import Body
from fastapi import Depends
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic import Field

from apps.web_api.artifacts import read_artifact
from apps.web_api.audit import read_audit_events
from apps.web_api.audit import record_audit_event
from apps.web_api.auth import auth_status as build_auth_status
from apps.web_api.auth import require_write_auth
from apps.web_api.backtest_candidates import read_backtest_candidate
from apps.web_api.deployment import build_deployment_status
from apps.web_api.jobs import collect_job_records, find_job_record, job_store, persist_job_queue_state
from apps.web_api.live_readiness_summary import build_live_readiness_summary
from apps.web_api.live_readiness_summary import record_live_readiness_disposition
from apps.web_api.hummingbot_status import build_hummingbot_paper_status
from apps.web_api.operation_guide import build_operation_guide
from apps.web_api.parameter_scans import list_parameter_scans
from apps.web_api.paper_observation_disposition import build_paper_observation_disposition
from apps.web_api.paper_observation_disposition import record_paper_observation_disposition
from apps.web_api.readiness_disposition import build_readiness_disposition
from apps.web_api.readiness_disposition import record_readiness_disposition
from apps.web_api.result_views import build_job_result_view
from apps.web_api.result_views import confirm_backtest_candidate
from apps.web_api.result_views import list_backtest_results
from apps.web_api.schedules import list_schedules as build_schedule_registry
from apps.web_api.schedules import upsert_schedule
from apps.web_api.state_db import build_state_db_status
from apps.web_api.status import REPO_ROOT
from apps.web_api.status import build_system_status
from apps.web_api.strategy_configs import list_strategy_configs
from apps.web_api.strategy_configs import read_strategy_config
from apps.web_api.strategy_configs import update_strategy_config
from apps.web_api.strategy_portfolios import list_strategy_portfolios
from apps.web_api.strategy_portfolios import upsert_strategy_portfolio
from apps.web_api.workflows import build_v0_workflow


app = FastAPI(title="Quant System Web API", version="0.1.0")
FRONTEND_DIST_DIR = REPO_ROOT / "apps/web_frontend/dist"


class StartJobRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class ConfirmBacktestCandidateRequest(BaseModel):
    job_id: str
    operator_note: str = ""


class RecordReadinessDispositionRequest(BaseModel):
    decision_id: str
    operator_note: str = ""


class RecordPaperObservationDispositionRequest(BaseModel):
    decision_id: str
    operator_note: str = ""


class RecordLiveReadinessDispositionRequest(BaseModel):
    decision_id: str
    operator_note: str = ""


class UpsertScheduleRequest(BaseModel):
    action_id: str
    interval_minutes: int
    enabled: bool = True
    parameters: dict[str, Any] = Field(default_factory=dict)


class UpdateStrategyConfigRequest(BaseModel):
    content: str
    operator_note: str = ""


class StrategyPortfolioMemberRequest(BaseModel):
    strategy_id: str
    weight: str
    enabled: bool = True


class UpsertStrategyPortfolioRequest(BaseModel):
    portfolio_id: str = "default_multi_strategy"
    members: list[StrategyPortfolioMemberRequest]
    operator_note: str = ""


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "quant-system-web-api",
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "frontend": "http://127.0.0.1:5173",
        "static_frontend": "/app",
        "endpoints": {
            "health": "/health",
            "auth": "/api/auth/status",
            "audit": "/api/audit",
            "deployment_status": "/api/deployment/status",
            "state_db_status": "/api/state-db/status",
            "system_status": "/api/system/status",
            "strategy_configs": "/api/strategy-configs",
            "strategy_portfolios": "/api/strategy-portfolios",
            "operation_guide": "/api/operation-guide",
            "workflow": "/api/workflows/v0",
            "jobs": "/api/jobs",
            "job_queue": "/api/jobs/queue",
            "backtest_results": "/api/backtests/results",
            "backtest_candidate": "/api/backtests/candidate",
            "parameter_scans": "/api/parameter-scans",
            "paper_readiness_disposition": "/api/paper-readiness/disposition",
            "paper_observation_disposition": "/api/paper-observation/disposition",
            "hummingbot_paper_status": "/api/hummingbot/paper-session/status",
            "schedules": "/api/schedules",
            "live_readiness_summary": "/api/live-readiness/summary",
            "live_readiness_disposition": "POST /api/live-readiness/disposition",
            "start_job": "POST /api/jobs/{action_id}",
            "cancel_job": "POST /api/jobs/{job_id}/cancel",
            "job_result_view": "/api/jobs/{job_id}/result-view",
            "artifact": "/api/artifacts?path=docs/web_dashboard.md",
        },
        "safe_actions": [
            "refresh_market_data",
            "query_strategy_data_quality",
            "run_backtest",
            "run_parameter_scan",
            "run_recommended_backtest",
            "run_candidate_walk_forward",
            "run_candidate_capacity_stress",
            "generate_paper_readiness",
            "run_paper_smoke",
            "generate_paper_observation_review",
            "run_hummingbot_sandbox_prepare",
            "run_hummingbot_runtime_preflight",
            "run_hummingbot_cli_direct_paper_handoff",
            "install_hummingbot_cli_direct_paper_files",
            "run_hummingbot_paper_session_control",
            "collect_hummingbot_paper_events",
            "run_hummingbot_export_acceptance",
            "run_hummingbot_observation_review",
            "generate_live_execution_package",
            "generate_live_post_trade_report",
            "generate_live_cooldown_review",
            "generate_live_initial_closure_report",
            "generate_live_position_exit_plan",
            "generate_external_alert_outbox",
        ],
        "blocked_actions": [
            "run_live_batch",
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "quant-system-web-api"}


@app.get("/api/auth/status")
def get_auth_status() -> dict[str, object]:
    return build_auth_status()


@app.get("/api/audit")
def get_audit() -> dict[str, object]:
    return read_audit_events()


@app.get("/api/deployment/status")
def get_deployment_status() -> dict[str, object]:
    return build_deployment_status()


@app.get("/api/state-db/status")
def get_state_db_status() -> dict[str, object]:
    return build_state_db_status()


@app.get("/api/system/status")
def system_status() -> dict[str, object]:
    return build_system_status()


@app.get("/api/strategy-configs")
def get_strategy_configs() -> dict[str, object]:
    return list_strategy_configs()


@app.get("/api/strategy-configs/{strategy_id}/{file_name}")
def get_strategy_config(strategy_id: str, file_name: str) -> dict[str, object]:
    try:
        return read_strategy_config(strategy_id=strategy_id, file_name=file_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/strategy-configs/{strategy_id}/{file_name}")
def post_strategy_config(
    strategy_id: str,
    file_name: str,
    request: UpdateStrategyConfigRequest,
    _: None = Depends(require_write_auth),
) -> dict[str, object]:
    try:
        payload = update_strategy_config(
            strategy_id=strategy_id,
            file_name=file_name,
            content=request.content,
            operator_note=request.operator_note,
        )
        record_audit_event(
            event_type="strategy_config_updated",
            target=f"{strategy_id}/{file_name}",
            payload=payload,
        )
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/strategy-portfolios")
def get_strategy_portfolios() -> dict[str, object]:
    return list_strategy_portfolios()


@app.post("/api/strategy-portfolios")
def post_strategy_portfolio(
    request: UpsertStrategyPortfolioRequest,
    _: None = Depends(require_write_auth),
) -> dict[str, object]:
    try:
        payload = upsert_strategy_portfolio(
            portfolio_id=request.portfolio_id,
            members=[item.model_dump() for item in request.members],
            operator_note=request.operator_note,
        )
        record_audit_event(
            event_type="strategy_portfolio_upserted",
            target=request.portfolio_id,
            payload=payload,
        )
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workflows/v0")
def v0_workflow() -> dict[str, object]:
    return build_v0_workflow(jobs=collect_job_records(job_store.list_jobs()))


@app.get("/api/operation-guide")
def get_operation_guide() -> dict[str, object]:
    workflow = build_v0_workflow(jobs=collect_job_records(job_store.list_jobs()))
    return build_operation_guide(workflow)


@app.get("/api/jobs")
def list_jobs() -> dict[str, object]:
    return {"jobs": collect_job_records(job_store.list_jobs())}


@app.get("/api/jobs/queue")
def get_job_queue() -> dict[str, object]:
    return persist_job_queue_state(job_store.list_jobs())


@app.get("/api/schedules")
def get_schedules() -> dict[str, object]:
    return build_schedule_registry()


@app.post("/api/schedules")
def post_schedule(request: UpsertScheduleRequest, _: None = Depends(require_write_auth)) -> dict[str, object]:
    try:
        record = upsert_schedule(
            action_id=request.action_id,
            interval_minutes=request.interval_minutes,
            enabled=request.enabled,
            parameters=request.parameters,
        )
        record_audit_event(event_type="schedule_upserted", target=request.action_id, payload=record)
        return record
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/backtests/results")
def get_backtest_results() -> dict[str, object]:
    return list_backtest_results(job_store.list_jobs())


@app.get("/api/parameter-scans")
def get_parameter_scans() -> dict[str, object]:
    return list_parameter_scans(job_store.list_jobs())


@app.get("/api/backtests/candidate")
def get_backtest_candidate() -> dict[str, object]:
    candidate = read_backtest_candidate()
    return {"candidate": candidate}


@app.post("/api/backtests/candidate")
def post_backtest_candidate(request: ConfirmBacktestCandidateRequest, _: None = Depends(require_write_auth)) -> dict[str, object]:
    try:
        candidate = confirm_backtest_candidate(
            request.job_id,
            job_store.list_jobs(),
            operator_note=request.operator_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if candidate is None:
        raise HTTPException(status_code=404, detail="backtest job not found")
    record_audit_event(event_type="backtest_candidate_confirmed", target=request.job_id, payload=candidate)
    return candidate


@app.get("/api/paper-readiness/disposition")
def get_paper_readiness_disposition() -> dict[str, object]:
    return build_readiness_disposition(job_store.list_jobs())


@app.post("/api/paper-readiness/disposition")
def post_paper_readiness_disposition(request: RecordReadinessDispositionRequest, _: None = Depends(require_write_auth)) -> dict[str, object]:
    try:
        payload = record_readiness_disposition(
            decision_id=request.decision_id,
            runtime_jobs=job_store.list_jobs(),
            operator_note=request.operator_note,
        )
        record_audit_event(event_type="paper_readiness_disposition", target=request.decision_id, payload=payload)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/paper-observation/disposition")
def get_paper_observation_disposition() -> dict[str, object]:
    return build_paper_observation_disposition(job_store.list_jobs())


@app.get("/api/hummingbot/paper-session/status")
def get_hummingbot_paper_session_status() -> dict[str, object]:
    return build_hummingbot_paper_status(jobs=job_store.list_jobs())


@app.post("/api/paper-observation/disposition")
def post_paper_observation_disposition(request: RecordPaperObservationDispositionRequest, _: None = Depends(require_write_auth)) -> dict[str, object]:
    try:
        payload = record_paper_observation_disposition(
            decision_id=request.decision_id,
            runtime_jobs=job_store.list_jobs(),
            operator_note=request.operator_note,
        )
        record_audit_event(event_type="paper_observation_disposition", target=request.decision_id, payload=payload)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/live-readiness/summary")
def get_live_readiness_summary() -> dict[str, object]:
    return build_live_readiness_summary()


@app.post("/api/live-readiness/disposition")
def post_live_readiness_disposition(request: RecordLiveReadinessDispositionRequest, _: None = Depends(require_write_auth)) -> dict[str, object]:
    try:
        payload = record_live_readiness_disposition(
            decision_id=request.decision_id,
            operator_note=request.operator_note,
        )
        record_audit_event(event_type="live_readiness_disposition", target=request.decision_id, payload=payload)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = find_job_record(job_id, job_store.list_jobs())
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/jobs/{job_id}/result-view")
def get_job_result_view(job_id: str) -> dict[str, object]:
    try:
        view = build_job_result_view(job_id, job_store.list_jobs())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if view is None:
        raise HTTPException(status_code=404, detail="job not found")
    return view


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, _: None = Depends(require_write_auth)) -> dict[str, object]:
    try:
        job = job_store.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        persisted = find_job_record(job_id, job_store.list_jobs())
        if persisted is None:
            raise HTTPException(status_code=404, detail="job not found")
        raise HTTPException(
            status_code=400,
            detail=f"job is not cancelable in status: {persisted.get('status', 'unknown')}",
        )
    payload = job.to_dict()
    record_audit_event(event_type="job_cancel_requested", target=job_id, payload=payload)
    return payload


@app.post("/api/jobs/{action_id}")
def start_job(
    action_id: str,
    request: StartJobRequest | None = Body(default=None),
    _: None = Depends(require_write_auth),
) -> dict[str, object]:
    try:
        job = job_store.start_job(action_id, parameters=request.parameters if request else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = job.to_dict()
    record_audit_event(event_type="job_started", target=action_id, payload={"job_id": job.job_id, "parameters": job.parameters})
    return payload


@app.get("/api/artifacts")
def get_artifact(path: str) -> dict[str, object]:
    try:
        return read_artifact(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if FRONTEND_DIST_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="web_frontend")
