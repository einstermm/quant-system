import "./styles.css";

type Alert = {
  severity: string;
  title: string;
  message: string;
  created_at: string;
};

type SystemStatus = {
  live: {
    status: string;
    next_decision: string;
    next_decision_reason: string;
    next_review_not_before: string;
  };
  position: {
    stance: string;
    trading_pair: string;
    strategy_net_base_quantity: string;
  };
};

type WorkflowArtifact = {
  label: string;
  path: string;
  kind: string;
  exists: boolean;
};

type ActionParameterOption = {
  label: string;
  value: string;
};

type ActionParameter = {
  name: string;
  label: string;
  input_type: "select" | "date" | "number" | "text" | "checkbox";
  default: string | number | boolean;
  help: string;
  required: boolean;
  options: ActionParameterOption[];
  min: string | null;
  max: string | null;
  step: string | null;
};

type WorkflowAction = {
  action_id: string;
  label: string;
  action_type: string;
  enabled: boolean;
  safety_level: string;
  description: string;
  blocked_reason: string;
  parameters: ActionParameter[];
  latest_job: JobSummary | null;
  runtime_alert: RuntimeAlert | null;
  output_dir_template: string;
};

type RuntimeAlert = {
  severity: "error" | "warning" | string;
  title: string;
  message: string;
  action_id: string;
  action_label: string;
  job_id: string;
  job_status: string;
  created_at: string;
};

type WorkflowStep = {
  step_id: string;
  phase: string;
  title: string;
  business_goal: string;
  status: string;
  base_status: string;
  runtime_status: "ok" | "warning" | "error" | string;
  decision: string;
  owner: string;
  inputs: WorkflowArtifact[];
  outputs: WorkflowArtifact[];
  actions: WorkflowAction[];
  runtime_alerts: RuntimeAlert[];
  notes: string[];
};

type Workflow = {
  workflow_id: string;
  title: string;
  mode: string;
  active_step_id: string;
  summary: {
    strategy_id: string;
    account_id: string;
    current_status: string;
    next_live_decision: string;
    next_live_reason: string;
    live_actions_exposed: boolean;
  };
  steps: WorkflowStep[];
};

type JobRecord = {
  job_id: string;
  action_id: string;
  label: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  artifacts: Record<string, string>;
  parameters: Record<string, string | number | boolean>;
  return_code: number | null;
  stdout: string;
  stderr: string;
  error: string;
  result_summary: JobResultSummary | null;
};

type JobQueueItem = {
  job_id: string;
  action_id: string;
  label: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  output_dir: string;
  metadata_path: string;
};

type JobQueueState = {
  path: string;
  queue_persistence_enabled: boolean;
  last_updated_at: string;
  active_statuses: string[];
  total_jobs: number;
  status_counts: Record<string, number>;
  active_actions: Record<string, string>;
  jobs: JobQueueItem[];
};

type StateDbDocument = {
  key: string;
  source_path: string;
  updated_at: string;
};

type StateDbStatus = {
  path: string;
  database_ready: boolean;
  tables: string[];
  document_count: number;
  audit_event_count: number;
  latest_audit_at: string;
  documents: StateDbDocument[];
};

type StrategyConfigFile = {
  file_name: string;
  path: string;
  exists: boolean;
  size_bytes: number;
  updated_at: string;
};

type StrategyConfigSummary = {
  strategy_id: string;
  label: string;
  path: string;
  files: StrategyConfigFile[];
};

type StrategyConfigsPayload = {
  allowed_files: string[];
  max_config_bytes: number;
  backup_root: string;
  strategies: StrategyConfigSummary[];
};

type StrategyConfigContent = {
  strategy_id: string;
  file_name: string;
  path: string;
  size_bytes: number;
  sha256: string;
  updated_at: string;
  content: string;
};

type StrategyPortfolioMember = {
  strategy_id: string;
  label: string;
  enabled: boolean;
  weight: string;
  strategy_path: string;
};

type StrategyPortfolio = {
  portfolio_id: string;
  updated_at: string;
  operator_note: string;
  members: StrategyPortfolioMember[];
  total_weight: string;
};

type StrategyPortfoliosPayload = {
  registry_path: string;
  supported_strategies: {strategy_id: string; path: string}[];
  portfolios: StrategyPortfolio[];
};

type OperationGuideStep = {
  order: number;
  step_id: string;
  phase: string;
  title: string;
  status: string;
  decision: string;
  is_current: boolean;
  runtime_alert_count: number;
  next_action_id: string;
  next_action_label: string;
  blocked_actions: {action_id: string; label: string; blocked_reason: string}[];
};

type OperationGuide = {
  title: string;
  workflow_id: string;
  active_step_id: string;
  current_step: OperationGuideStep | null;
  steps: OperationGuideStep[];
  safety_notes: string[];
};

type JobSummary = {
  job_id: string;
  action_id: string;
  label: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  artifacts: Record<string, string>;
  parameters: Record<string, string | number | boolean>;
  return_code: number | null;
  result_summary: JobResultSummary | null;
};

type JobResultSummary = {
  kind: string;
  title: string;
  metrics: ResultMetric[];
};

type ResultMetric = {
  label: string;
  value: string;
};

type BacktestResultView = {
  job_id: string;
  kind: "backtest";
  strategy_id: string;
  artifact_path: string;
  parameters: Record<string, string>;
  metrics: ResultMetric[];
  series: BacktestSeriesPoint[];
  series_count: number;
  series_truncated: boolean;
  trades: BacktestTrade[];
  trade_count: number;
  trades_truncated: boolean;
  monthly_returns: BacktestMonthlyReturn[];
  drawdown_episodes: BacktestDrawdownEpisode[];
  trade_stats: Record<string, string>;
};

type PaperSmokeResultView = {
  job_id: string;
  kind: "paper_smoke";
  artifact_path: string;
  parameters: Record<string, string>;
  summary: Record<string, string>;
  metrics: ResultMetric[];
  series: ResultSeriesPoint[];
  series_count: number;
  series_truncated: boolean;
  cycles: PaperSmokeCycle[];
  cycle_count: number;
  cycles_truncated: boolean;
  orders: PaperSmokeOrder[];
  order_count: number;
  orders_truncated: boolean;
  ledger_orders: PaperLedgerOrder[];
  ledger_order_count: number;
  ledger_orders_truncated: boolean;
};

type HummingbotEventRow = {
  timestamp: string;
  event_type: string;
  client_order_id: string;
  trading_pair: string;
  side: string;
  status: string;
  price: string;
  amount: string;
  message: string;
};

type HummingbotEventTypeRow = {
  event_type: string;
  count: string;
};

type HummingbotEventsResultView = {
  job_id: string;
  kind: "hummingbot_events";
  artifact_path: string;
  events_artifact_path: string;
  parameters: Record<string, string>;
  metrics: ResultMetric[];
  event_types: HummingbotEventTypeRow[];
  events: HummingbotEventRow[];
  event_count: number;
  events_truncated: boolean;
};

type HummingbotAcceptanceResultView = {
  job_id: string;
  kind: "hummingbot_acceptance";
  artifact_path: string;
  events_artifact_path: string;
  parameters: Record<string, string>;
  metrics: ResultMetric[];
  event_types: HummingbotEventTypeRow[];
  events: HummingbotEventRow[];
  event_count: number;
  events_truncated: boolean;
};

type JobResultView =
  | BacktestResultView
  | PaperSmokeResultView
  | HummingbotEventsResultView
  | HummingbotAcceptanceResultView;

type ResultSeriesPoint = {
  timestamp: string;
  equity: number;
  drawdown: number;
};

type BacktestSeriesPoint = {
  timestamp: string;
  equity: number;
  drawdown: number;
};

type BacktestTrade = {
  timestamp: string;
  symbol: string;
  side: string;
  price: string;
  quantity: string;
  notional: string;
  fee: string;
  target_weight: string;
};

type BacktestMonthlyReturn = {
  month: string;
  start_equity: string;
  end_equity: string;
  return: string;
};

type BacktestDrawdownEpisode = {
  start: string;
  trough: string;
  recovered_at: string;
  status: string;
  trough_drawdown: string;
};

type PaperSmokeCycle = {
  cycle_number: string;
  started_at: string;
  completed_at: string;
  status: string;
  equity: string;
  cash: string;
  gross_exposure: string;
  routed_order_count: string;
  approved_order_count: string;
  rejected_order_count: string;
  market_data_complete: string;
  error: string;
};

type PaperSmokeOrder = {
  cycle_number: string;
  completed_at: string;
  intent_id: string;
  risk_status: string;
  risk_reason: string;
  external_order_id: string;
};

type PaperLedgerOrder = {
  created_at: string;
  paper_order_id: string;
  intent_id: string;
  symbol: string;
  side: string;
  quantity: string;
  fill_price: string;
  notional: string;
  fee: string;
  status: string;
};


type BacktestResultsPayload = {
  results: BacktestResultItem[];
  candidate: BacktestCandidate | null;
  candidate_path: string;
};

type BacktestResultItem = {
  job_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  strategy_id: string;
  artifact_path: string;
  parameters: Record<string, string>;
  metrics: Record<string, string>;
  quality_gate?: CandidateQualityGate;
  equivalence?: EquivalenceInfo;
  selected_as_candidate: boolean;
};

type BacktestCandidate = BacktestResultItem & {
  candidate_type: string;
  selected_at: string;
  operator_note: string;
};

type CandidateQualityGate = {
  status: string;
  failed_count: number;
  message: string;
  gates: CandidateQualityGateItem[];
};

type CandidateQualityGateItem = {
  gate_id: string;
  label: string;
  metric_key: string;
  operator: string;
  threshold: string;
  observed: string;
  unit: "percent" | "number" | string;
  status: string;
};

type EquivalenceInfo = {
  status: string;
  group_key: string;
  equivalent_count: number;
  equivalent_ids: string[];
  message: string;
};

type ParameterScanPayload = {
  scans: ParameterScanItem[];
  latest_scan: ParameterScanItem | null;
};

type ParameterScanItem = {
  job_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  strategy_id: string;
  experiment_id: string;
  artifact_path: string;
  summary_csv_path: string;
  selection_policy: Record<string, string>;
  run_count: number;
  best_run: ParameterScanRun | null;
  recommendations: ParameterScanRun[];
};

type ParameterScanRun = {
  rank: number | string;
  run_id: string;
  parameters: Record<string, string>;
  metrics: Record<string, string>;
  recommendation: string;
  equivalence?: EquivalenceInfo;
};

type ReadinessDisposition = {
  status: string;
  latest_job: ReadinessJobSummary | null;
  readiness_artifact: string;
  candidate: ReadinessCandidate | null;
  alerts: ReadinessAlert[];
  critical_alerts: number;
  warning_alerts: number;
  recommended_actions: string[];
  repair_guidance: ReadinessRepairGuidance[];
  disposition_options: ReadinessDispositionOption[];
  recorded_disposition: RecordedDisposition | null;
  disposition_resolution: DispositionResolution;
};

type ReadinessJobSummary = {
  job_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  artifacts: Record<string, string>;
  parameters: Record<string, string | number | boolean>;
};

type ReadinessCandidate = {
  job_id: string;
  strategy_id: string;
  artifact_path: string;
  metrics?: Record<string, string>;
};

type ReadinessAlert = {
  severity: string;
  title: string;
  message: string;
  created_at: string;
  hint: string;
};

type ReadinessDispositionOption = {
  decision_id: string;
  label: string;
  description: string;
  target_step_id: string;
  severity: string;
  enabled: boolean;
};

type ReadinessRepairGuidance = {
  guidance_id: string;
  label: string;
  description: string;
  target_step_id: string;
  action_id: string;
  severity: string;
  enabled: boolean;
};

type RecordedDisposition = {
  decision_id: string;
  label: string;
  recorded_at: string;
  operator_note: string;
  readiness_status: string;
  latest_readiness_job_id: string;
  candidate_job_id: string;
  candidate_strategy_id: string;
  next_step_id: string;
  resolution_status: string;
  recorded_candidate_job_id: string;
  current_candidate_job_id: string;
  superseded_by_candidate_job_id: string;
  message: string;
};

type DispositionResolution = {
  resolution_status: string;
  recorded_candidate_job_id: string;
  current_candidate_job_id: string;
  superseded_by_candidate_job_id: string;
  message: string;
};

type PaperObservationDisposition = {
  status: string;
  latest_job: PaperObservationJobSummary | null;
  summary_artifact: string;
  observation_artifact: string;
  ledger_artifact: string;
  summary: Record<string, string>;
  alerts: ReadinessAlert[];
  recommended_actions: string[];
  disposition_options: ReadinessDispositionOption[];
  recorded_disposition: PaperObservationRecordedDisposition | null;
};

type PaperObservationJobSummary = {
  job_id: string;
  action_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
};

type PaperObservationRecordedDisposition = {
  decision_id: string;
  label: string;
  recorded_at: string;
  operator_note: string;
  observation_status: string;
  latest_observation_job_id: string;
  summary_artifact: string;
  next_step_id: string;
};

type HummingbotPaperStatus = {
  status: string;
  state: Record<string, string | number | boolean>;
  state_path: string;
  state_exists: boolean;
  event_log: {
    path: string;
    exists: boolean;
    size_bytes: number;
    line_count: number;
    parse_errors: number;
    first_event_type: string;
    first_timestamp: string;
    last_event_type: string;
    last_timestamp: string;
  };
  latest_control_job: Record<string, string | Record<string, string>>;
  latest_install_job: Record<string, string | Record<string, string>>;
  process_started_by_web: boolean;
  live_order_submission_exposed: boolean;
  recommended_actions: string[];
};

type LiveReadinessSummary = {
  status: string;
  live_actions_exposed: boolean;
  live_order_submission_exposed: boolean;
  live_runner_exposed: boolean;
  next_live_decision: string;
  next_live_reason: string;
  next_review_not_before: string;
  reports: LiveReadinessReport[];
  blockers: LiveReadinessBlocker[];
  recommended_actions: string[];
  disposition_options: ReadinessDispositionOption[];
  recorded_disposition: LiveReadinessRecordedDisposition | null;
};

type LiveReadinessReport = {
  report_id: string;
  label: string;
  path: string;
  exists: boolean;
  decision: string;
  generated_at: string;
  alerts: number;
  critical_alerts: number;
  warning_alerts: number;
};

type LiveReadinessBlocker = {
  report_id: string;
  title: string;
  message: string;
  severity: string;
};

type LiveReadinessRecordedDisposition = {
  decision_id: string;
  label: string;
  recorded_at: string;
  operator_note: string;
  live_summary_status: string;
  next_live_decision: string;
  next_step_id: string;
  live_runner_exposed: boolean;
  live_order_submission_exposed: boolean;
};

type TerminalAction = {
  action_id: string;
  label: string;
  description: string;
  safety_level: string;
  enabled: boolean;
  blocked_reason: string;
};

type TerminalBlocker = {
  severity: string;
  title: string;
  message: string;
  source: string;
};

type TerminalCandidateOrder = {
  client_order_id: string;
  trading_pair: string;
  side: string;
  order_type: string;
  notional_quote: string;
  estimated_price: string;
  estimated_quantity: string;
  signal_timestamp: string;
  signal_momentum: string;
  risk_checks: {
    inside_allowlist: boolean;
    max_order_notional: string;
    max_batch_notional: string;
    live_order_submission_armed: boolean;
  };
};

type TradingTerminal = {
  generated_at: string;
  mode: {
    status: string;
    label: string;
    reason: string;
    next_live_decision: string;
  };
  safety: {
    web_mode: string;
    live_trading_enabled: boolean;
    global_kill_switch: boolean;
    alert_channel_configured: boolean;
    exchange_key_env_detected: boolean;
    live_runner_exposed: boolean;
    live_order_submission_exposed: boolean;
    web_can_submit_live_order: boolean;
    live_order_submission_armed: boolean;
    runner_package_exists: boolean;
    runner_disarmed: boolean;
  };
  account: {
    account_id: string;
    connector: string;
    market_type: string;
    allowed_pairs: string[];
  };
  strategy: {
    strategy_id: string;
    signal_summary: Record<string, unknown>;
  };
  position: {
    stance: string;
    trading_pair: string;
    strategy_net_base_quantity: string;
    strategy_gross_base_quantity: string;
    entry_cost_basis_quote: string;
    entry_average_price_quote: string;
    account_ending_base_balance: string;
    fee_amount: string;
    fee_asset: string;
    exit_requires_activation: boolean;
    exit_plan: string;
    hold_until: string;
  };
  candidate_orders: {
    package_path: string;
    package_exists: boolean;
    decision: string;
    generated_at: string;
    execution_runner_generated: boolean;
    live_order_submission_armed: boolean;
    orders: TerminalCandidateOrder[];
    checklist: {item_id: string; title: string; status: string; details: string}[];
  };
  risk: {
    summary: Record<string, string | number | boolean>;
    allowed_pairs: string[];
    checks: Record<string, string | number | boolean | string[]>;
  };
  execution: {
    status: string;
    generated_at: string;
    order_checks: Record<string, string | number | boolean | string[]>;
    fill_summary: Record<string, string>;
    balance_checks: Record<string, string | Record<string, string> | string[]>;
    operational_checks: Record<string, string | number | boolean>;
    runner: {
      package_exists: boolean;
      decision: string;
      live_order_submission_armed: boolean;
    };
  };
  hummingbot: HummingbotPaperStatus;
  blockers: TerminalBlocker[];
  actions: TerminalAction[];
  artifacts: Record<string, string>;
};

type ArtifactContent = {
  path: string;
  exists: boolean;
  kind: string;
  size_bytes: number;
  truncated: boolean;
  content: string;
  error: string;
};

type PendingConfirmation = {
  stepId: string;
  actionId: string;
  parameters: Record<string, string | number | boolean>;
};

type AppState = {
  status: SystemStatus;
  tradingTerminal: TradingTerminal;
  workflow: Workflow;
  jobs: JobRecord[];
  jobQueue: JobQueueState;
  stateDb: StateDbStatus;
  strategyConfigs: StrategyConfigsPayload;
  selectedStrategyConfig: StrategyConfigContent | null;
  strategyPortfolios: StrategyPortfoliosPayload;
  operationGuide: OperationGuide;
  backtestResults: BacktestResultsPayload;
  parameterScans: ParameterScanPayload;
  readinessDisposition: ReadinessDisposition;
  paperObservationDisposition: PaperObservationDisposition;
  hummingbotPaperStatus: HummingbotPaperStatus;
  liveReadinessSummary: LiveReadinessSummary;
  selectedBacktestIds: string[];
  pendingCandidateConfirmation: BacktestResultItem | null;
  artifact: ArtifactContent | null;
  pendingConfirmation: PendingConfirmation | null;
  selectedJob: JobRecord | null;
  selectedResultView: JobResultView | null;
  resultViewError: string;
  selectedStepId: string;
  actionMessage: string;
};

const appRoot = requireElement(document.querySelector<HTMLDivElement>("#app"));
const apiBase =
  import.meta.env.VITE_API_BASE_URL ??
  (window.location.port === "5173" ? "http://127.0.0.1:8000" : "");
const numberFormatter = new Intl.NumberFormat("zh-CN", {maximumFractionDigits: 2});
const percentFormatter = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
  style: "percent",
});
let state: AppState | null = null;

renderLoading();
loadPage().catch((error: unknown) => {
  renderError(error instanceof Error ? error.message : String(error));
});

appRoot.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const terminalActionButton = target.closest<HTMLButtonElement>("[data-terminal-action-id]");
  if (terminalActionButton && state) {
    const actionId = terminalActionButton.dataset.terminalActionId ?? "";
    const action = state.tradingTerminal.actions.find((item) => item.action_id === actionId);
    if (!action) {
      return;
    }
    if (!action.enabled) {
      state = {
        ...state,
        actionMessage: `${action.label}：${action.blocked_reason || "当前不可执行。"}`,
      };
      renderApp(state);
      return;
    }
    const activeJob = activeJobForAction(state.jobs, action.action_id);
    if (activeJob) {
      state = {
        ...state,
        selectedJob: activeJob,
        selectedResultView: null,
        resultViewError: "",
        actionMessage: `${action.label} 已有运行中任务：${activeJob.job_id}`,
      };
      renderApp(state);
      return;
    }
    state = {
      ...state,
      pendingConfirmation: {
        stepId: "terminal",
        actionId: action.action_id,
        parameters: {},
      },
      actionMessage: "请确认本次终端安全动作。",
    };
    renderApp(state);
    return;
  }

  const readinessDispositionButton = target.closest<HTMLButtonElement>("[data-readiness-disposition-id]");
  if (readinessDispositionButton && state) {
    recordReadinessDisposition(readinessDispositionButton.dataset.readinessDispositionId ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const paperObservationDispositionButton = target.closest<HTMLButtonElement>("[data-paper-observation-disposition-id]");
  if (paperObservationDispositionButton && state) {
    recordPaperObservationDisposition(paperObservationDispositionButton.dataset.paperObservationDispositionId ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const liveReadinessDispositionButton = target.closest<HTMLButtonElement>("[data-live-readiness-disposition-id]");
  if (liveReadinessDispositionButton && state) {
    recordLiveReadinessDisposition(liveReadinessDispositionButton.dataset.liveReadinessDispositionId ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const toggleBacktestButton = target.closest<HTMLButtonElement>("[data-toggle-backtest-id]");
  if (toggleBacktestButton && state) {
    toggleBacktestComparison(toggleBacktestButton.dataset.toggleBacktestId ?? "");
    return;
  }

  const openConfigButton = target.closest<HTMLButtonElement>("[data-config-strategy-id]");
  if (openConfigButton && state) {
    loadStrategyConfig(
      openConfigButton.dataset.configStrategyId ?? "",
      openConfigButton.dataset.configFileName ?? "",
    ).catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const saveConfigButton = target.closest<HTMLButtonElement>("[data-save-strategy-config]");
  if (saveConfigButton && state?.selectedStrategyConfig) {
    const editor = appRoot.querySelector<HTMLTextAreaElement>("#strategy-config-content");
    updateStrategyConfig(state.selectedStrategyConfig, editor?.value ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const closeConfigButton = target.closest<HTMLButtonElement>("[data-close-strategy-config]");
  if (closeConfigButton && state) {
    state = {...state, selectedStrategyConfig: null, actionMessage: "已关闭策略配置编辑。"};
    renderApp(state);
    return;
  }

  const savePortfolioButton = target.closest<HTMLButtonElement>("[data-save-strategy-portfolio]");
  if (savePortfolioButton && state) {
    saveStrategyPortfolio().catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const prepareBacktestCandidateButton = target.closest<HTMLButtonElement>("[data-prepare-backtest-candidate-id]");
  if (prepareBacktestCandidateButton && state) {
    prepareBacktestCandidateConfirmation(prepareBacktestCandidateButton.dataset.prepareBacktestCandidateId ?? "");
    return;
  }

  const cancelCandidateButton = target.closest<HTMLButtonElement>("[data-cancel-candidate-confirm]");
  if (cancelCandidateButton && state) {
    state = {...state, pendingCandidateConfirmation: null, actionMessage: "已取消候选确认。"};
    renderApp(state);
    return;
  }

  const confirmBacktestButton = target.closest<HTMLButtonElement>("[data-confirm-candidate-id]");
  if (confirmBacktestButton && state) {
    confirmBacktestCandidate(confirmBacktestButton.dataset.confirmCandidateId ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        pendingCandidateConfirmation: null,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const recommendedBacktestButton = target.closest<HTMLButtonElement>("[data-recommended-scan-job-id]");
  if (recommendedBacktestButton && state) {
    startRecommendedBacktest(
      recommendedBacktestButton.dataset.recommendedScanJobId ?? "",
      recommendedBacktestButton.dataset.recommendedRunId ?? "",
    ).catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const artifactButton = target.closest<HTMLButtonElement>("[data-artifact-path]");
  if (artifactButton && state) {
    loadArtifact(artifactButton.dataset.artifactPath ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const cancelJobButton = target.closest<HTMLButtonElement>("[data-cancel-job-id]");
  if (cancelJobButton && state) {
    cancelJob(cancelJobButton.dataset.cancelJobId ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const jobButton = target.closest<HTMLButtonElement>("[data-job-id]");
  if (jobButton && state) {
    loadJobDetail(jobButton.dataset.jobId ?? "").catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const closeJobButton = target.closest<HTMLButtonElement>("[data-close-job-detail]");
  if (closeJobButton && state) {
    state = {...state, selectedJob: null, selectedResultView: null, resultViewError: "", actionMessage: ""};
    renderApp(state);
    return;
  }

  const cancelConfirmButton = target.closest<HTMLButtonElement>("[data-cancel-confirm]");
  if (cancelConfirmButton && state) {
    state = {...state, pendingConfirmation: null, actionMessage: "已取消任务启动。"};
    renderApp(state);
    return;
  }

  const confirmButton = target.closest<HTMLButtonElement>("[data-confirm-action-id]");
  if (confirmButton && state?.pendingConfirmation) {
    const confirmation = state.pendingConfirmation;
    if (confirmation.actionId !== confirmButton.dataset.confirmActionId) {
      return;
    }
    startJob(confirmation.actionId, confirmation.parameters).catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        pendingConfirmation: null,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
    return;
  }

  const stepButton = target.closest<HTMLButtonElement>("[data-step-id]");
  if (stepButton && state) {
    state = {
      ...state,
      selectedStepId: stepButton.dataset.stepId ?? state.selectedStepId,
      pendingConfirmation: null,
      pendingCandidateConfirmation: null,
      actionMessage: "",
    };
    renderApp(state);
    return;
  }

  const prepareActionButton = target.closest<HTMLButtonElement>("[data-prepare-action-id]");
  if (prepareActionButton && state) {
    const action = selectedStep(state).actions.find(
      (item) => item.action_id === prepareActionButton.dataset.prepareActionId,
    );
    if (!action) {
      return;
    }
    if (!action.enabled || action.action_type !== "start_job") {
      state = {
        ...state,
        actionMessage: `${action.label}：${action.blocked_reason || "当前不可执行。"}`,
      };
      renderApp(state);
      return;
    }
    const activeJob = activeJobForAction(state.jobs, action.action_id);
    if (activeJob) {
      state = {
        ...state,
        selectedJob: activeJob,
        selectedResultView: null,
        resultViewError: "",
        actionMessage: `${action.label} 已有运行中任务：${activeJob.job_id}`,
      };
      renderApp(state);
      return;
    }
    const parameters = collectActionParameters(action.action_id);
    state = {
      ...state,
      pendingConfirmation: {
        stepId: state.selectedStepId,
        actionId: action.action_id,
        parameters,
      },
      actionMessage: "请确认本次任务参数和输出位置。",
    };
    renderApp(state);
    return;
  }

  const actionButton = target.closest<HTMLButtonElement>("[data-action-id]");
  if (actionButton && state) {
    const action = selectedStep(state).actions.find(
      (item) => item.action_id === actionButton.dataset.actionId,
    );
    if (!action) {
      return;
    }
    if (!action.enabled || action.action_type !== "start_job") {
      state = {
        ...state,
        actionMessage: `${action.label}：${action.blocked_reason || "当前不可执行。"}`,
      };
      renderApp(state);
      return;
    }
    const parameters = collectActionParameters(action.action_id);
    startJob(action.action_id, parameters).catch((error: unknown) => {
      if (!state) return;
      state = {
        ...state,
        actionMessage: error instanceof Error ? error.message : String(error),
      };
      renderApp(state);
    });
  }
});

appRoot.addEventListener("submit", (event) => {
  event.preventDefault();
});

async function loadPage(): Promise<void> {
  const {status, tradingTerminal, workflow, jobs, jobQueue, stateDb, strategyConfigs, strategyPortfolios, operationGuide, backtestResults, parameterScans, readinessDisposition, paperObservationDisposition, hummingbotPaperStatus, liveReadinessSummary} = await fetchRuntimeState();
  state = {
    status,
    tradingTerminal,
    workflow,
    jobs,
    jobQueue,
    stateDb,
    strategyConfigs,
    selectedStrategyConfig: null,
    strategyPortfolios,
    operationGuide,
    backtestResults,
    parameterScans,
    readinessDisposition,
    paperObservationDisposition,
    hummingbotPaperStatus,
    liveReadinessSummary,
    selectedBacktestIds: defaultBacktestSelection(backtestResults),
    pendingCandidateConfirmation: null,
    artifact: null,
    pendingConfirmation: null,
    selectedJob: null,
    selectedResultView: null,
    resultViewError: "",
    selectedStepId: workflow.active_step_id || workflow.steps[0]?.step_id || "",
    actionMessage: "",
  };
  renderApp(state);
}

async function fetchRuntimeState(): Promise<{
  status: SystemStatus;
  tradingTerminal: TradingTerminal;
  workflow: Workflow;
  jobs: JobRecord[];
  jobQueue: JobQueueState;
  stateDb: StateDbStatus;
  strategyConfigs: StrategyConfigsPayload;
  strategyPortfolios: StrategyPortfoliosPayload;
  operationGuide: OperationGuide;
  backtestResults: BacktestResultsPayload;
  parameterScans: ParameterScanPayload;
  readinessDisposition: ReadinessDisposition;
  paperObservationDisposition: PaperObservationDisposition;
  hummingbotPaperStatus: HummingbotPaperStatus;
  liveReadinessSummary: LiveReadinessSummary;
}> {
  const [
    statusResponse,
    tradingTerminalResponse,
    workflowResponse,
    jobsResponse,
    jobQueueResponse,
    stateDbResponse,
    strategyConfigsResponse,
    strategyPortfoliosResponse,
    operationGuideResponse,
    backtestResponse,
    parameterScansResponse,
    readinessDispositionResponse,
    paperObservationDispositionResponse,
    hummingbotPaperStatusResponse,
    liveReadinessSummaryResponse,
  ] = await Promise.all([
    fetch(`${apiBase}/api/system/status`),
    fetch(`${apiBase}/api/trading-terminal`),
    fetch(`${apiBase}/api/workflows/v0`),
    fetch(`${apiBase}/api/jobs`),
    fetch(`${apiBase}/api/jobs/queue`),
    fetch(`${apiBase}/api/state-db/status`),
    fetch(`${apiBase}/api/strategy-configs`),
    fetch(`${apiBase}/api/strategy-portfolios`),
    fetch(`${apiBase}/api/operation-guide`),
    fetch(`${apiBase}/api/backtests/results`),
    fetch(`${apiBase}/api/parameter-scans`),
    fetch(`${apiBase}/api/paper-readiness/disposition`),
    fetch(`${apiBase}/api/paper-observation/disposition`),
    fetch(`${apiBase}/api/hummingbot/paper-session/status`),
    fetch(`${apiBase}/api/live-readiness/summary`),
  ]);
  if (!statusResponse.ok) {
    throw new Error(`状态 API 请求失败：${statusResponse.status} ${statusResponse.statusText}`);
  }
  if (!tradingTerminalResponse.ok) {
    throw new Error(`交易终端 API 请求失败：${tradingTerminalResponse.status} ${tradingTerminalResponse.statusText}`);
  }
  if (!workflowResponse.ok) {
    throw new Error(`流程 API 请求失败：${workflowResponse.status} ${workflowResponse.statusText}`);
  }
  if (!backtestResponse.ok) {
    throw new Error(`回测结果 API 请求失败：${backtestResponse.status} ${backtestResponse.statusText}`);
  }
  if (!jobQueueResponse.ok) {
    throw new Error(`任务队列 API 请求失败：${jobQueueResponse.status} ${jobQueueResponse.statusText}`);
  }
  if (!stateDbResponse.ok) {
    throw new Error(`状态数据库 API 请求失败：${stateDbResponse.status} ${stateDbResponse.statusText}`);
  }
  if (!strategyConfigsResponse.ok) {
    throw new Error(`策略配置 API 请求失败：${strategyConfigsResponse.status} ${strategyConfigsResponse.statusText}`);
  }
  if (!strategyPortfoliosResponse.ok) {
    throw new Error(`策略组合 API 请求失败：${strategyPortfoliosResponse.status} ${strategyPortfoliosResponse.statusText}`);
  }
  if (!operationGuideResponse.ok) {
    throw new Error(`操作向导 API 请求失败：${operationGuideResponse.status} ${operationGuideResponse.statusText}`);
  }
  if (!parameterScansResponse.ok) {
    throw new Error(`参数扫描 API 请求失败：${parameterScansResponse.status} ${parameterScansResponse.statusText}`);
  }
  if (!readinessDispositionResponse.ok) {
    throw new Error(
      `准入处置 API 请求失败：${readinessDispositionResponse.status} ${readinessDispositionResponse.statusText}`,
    );
  }
  if (!paperObservationDispositionResponse.ok) {
    throw new Error(
      `Paper 观察处置 API 请求失败：${paperObservationDispositionResponse.status} ${paperObservationDispositionResponse.statusText}`,
    );
  }
  if (!liveReadinessSummaryResponse.ok) {
    throw new Error(
      `Live 准入摘要 API 请求失败：${liveReadinessSummaryResponse.status} ${liveReadinessSummaryResponse.statusText}`,
    );
  }
  if (!hummingbotPaperStatusResponse.ok) {
    throw new Error(
      `Hummingbot 状态 API 请求失败：${hummingbotPaperStatusResponse.status} ${hummingbotPaperStatusResponse.statusText}`,
    );
  }
  const status = (await statusResponse.json()) as SystemStatus;
  const tradingTerminal = (await tradingTerminalResponse.json()) as TradingTerminal;
  const workflow = (await workflowResponse.json()) as Workflow;
  const jobsPayload = (await jobsResponse.json()) as { jobs: JobRecord[] };
  const jobQueue = (await jobQueueResponse.json()) as JobQueueState;
  const stateDb = (await stateDbResponse.json()) as StateDbStatus;
  const strategyConfigs = (await strategyConfigsResponse.json()) as StrategyConfigsPayload;
  const strategyPortfolios = (await strategyPortfoliosResponse.json()) as StrategyPortfoliosPayload;
  const operationGuide = (await operationGuideResponse.json()) as OperationGuide;
  const backtestResults = (await backtestResponse.json()) as BacktestResultsPayload;
  const parameterScans = (await parameterScansResponse.json()) as ParameterScanPayload;
  const readinessDisposition = (await readinessDispositionResponse.json()) as ReadinessDisposition;
  const paperObservationDisposition = (await paperObservationDispositionResponse.json()) as PaperObservationDisposition;
  const hummingbotPaperStatus = (await hummingbotPaperStatusResponse.json()) as HummingbotPaperStatus;
  const liveReadinessSummary = (await liveReadinessSummaryResponse.json()) as LiveReadinessSummary;
  return {status, tradingTerminal, workflow, jobs: jobsPayload.jobs, jobQueue, stateDb, strategyConfigs, strategyPortfolios, operationGuide, backtestResults, parameterScans, readinessDisposition, paperObservationDisposition, hummingbotPaperStatus, liveReadinessSummary};
}

async function refreshRuntimeState(message = ""): Promise<void> {
  const previous = state;
  if (!previous) return;
  const {status, tradingTerminal, workflow, jobs, jobQueue, stateDb, strategyConfigs, strategyPortfolios, operationGuide, backtestResults, parameterScans, readinessDisposition, paperObservationDisposition, hummingbotPaperStatus, liveReadinessSummary} = await fetchRuntimeState();
  const stepStillExists = workflow.steps.some((step) => step.step_id === previous.selectedStepId);
  const selectedJob = previous.selectedJob
    ? jobs.find((job) => job.job_id === previous.selectedJob?.job_id) ?? previous.selectedJob
    : null;
  const sameSelectedJob = selectedJob?.job_id === previous.selectedJob?.job_id;
  const backtestIds = new Set(backtestResults.results.map((item) => item.job_id));
  const selectedBacktestIds = previous.selectedBacktestIds.filter((jobId) => backtestIds.has(jobId));
  state = {
    ...previous,
    status,
    tradingTerminal,
    workflow,
    jobs,
    jobQueue,
    stateDb,
    strategyConfigs,
    strategyPortfolios,
    operationGuide,
    backtestResults,
    parameterScans,
    readinessDisposition,
    paperObservationDisposition,
    hummingbotPaperStatus,
    liveReadinessSummary,
    selectedBacktestIds: selectedBacktestIds.length ? selectedBacktestIds : defaultBacktestSelection(backtestResults),
    pendingCandidateConfirmation: previous.pendingCandidateConfirmation,
    selectedJob,
    selectedResultView: sameSelectedJob ? previous.selectedResultView : null,
    resultViewError: sameSelectedJob ? previous.resultViewError : "",
    selectedStepId: stepStillExists
      ? previous.selectedStepId
      : workflow.active_step_id || workflow.steps[0]?.step_id || "",
    actionMessage: message || previous.actionMessage,
  };
  renderApp(state);
}

async function loadArtifact(path: string): Promise<void> {
  if (!state || !path) return;
  state = {...state, actionMessage: `正在读取产物：${path}`};
  renderApp(state);
  const response = await fetch(`${apiBase}/api/artifacts?path=${encodeURIComponent(path)}`);
  if (!response.ok) {
    throw new Error(`产物读取失败：${response.status} ${response.statusText}`);
  }
  const artifact = (await response.json()) as ArtifactContent;
  state = {
    ...state,
    artifact,
    actionMessage: artifact.error ? artifact.error : `已读取产物：${artifact.path}`,
  };
  renderApp(state);
}

async function loadStrategyConfig(strategyId: string, fileName: string): Promise<void> {
  if (!state || !strategyId || !fileName) return;
  state = {...state, actionMessage: `正在读取策略配置：${strategyId}/${fileName}`};
  renderApp(state);
  const response = await fetch(
    `${apiBase}/api/strategy-configs/${encodeURIComponent(strategyId)}/${encodeURIComponent(fileName)}`,
  );
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "策略配置读取失败"));
  }
  const payload = (await response.json()) as StrategyConfigContent;
  state = {
    ...state,
    selectedStrategyConfig: payload,
    actionMessage: `已读取策略配置：${payload.path}`,
  };
  renderApp(state);
}

async function updateStrategyConfig(config: StrategyConfigContent, content: string): Promise<void> {
  if (!state) return;
  state = {...state, actionMessage: `正在保存策略配置：${config.strategy_id}/${config.file_name}`};
  renderApp(state);
  const response = await fetch(
    `${apiBase}/api/strategy-configs/${encodeURIComponent(config.strategy_id)}/${encodeURIComponent(config.file_name)}`,
    {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({content, operator_note: "web edit"}),
    },
  );
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "策略配置保存失败"));
  }
  await refreshRuntimeState(`策略配置已保存：${config.path}`);
  await loadStrategyConfig(config.strategy_id, config.file_name);
}

async function saveStrategyPortfolio(): Promise<void> {
  if (!state) return;
  const enabledByStrategy = new Map(
    Array.from(appRoot.querySelectorAll<HTMLInputElement>("[data-portfolio-enabled]")).map((input) => [
      input.dataset.portfolioEnabled ?? "",
      input.checked,
    ]),
  );
  const members = Array.from(appRoot.querySelectorAll<HTMLInputElement>("[data-portfolio-weight]")).map((input) => {
    const strategyId = input.dataset.portfolioWeight ?? "";
    return {
      strategy_id: strategyId,
      weight: input.value,
      enabled: enabledByStrategy.get(strategyId) ?? true,
    };
  });
  state = {...state, actionMessage: "正在保存多策略组合。"};
  renderApp(state);
  const response = await fetch(`${apiBase}/api/strategy-portfolios`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      portfolio_id: "default_multi_strategy",
      members,
      operator_note: "web portfolio edit",
    }),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "策略组合保存失败"));
  }
  await refreshRuntimeState("多策略组合已保存。");
}

async function loadJobDetail(jobId: string): Promise<void> {
  if (!state || !jobId) return;
  state = {...state, actionMessage: `正在读取任务详情：${jobId}`};
  renderApp(state);

  const response = await fetch(`${apiBase}/api/jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "任务详情读取失败"));
  }
  const job = (await response.json()) as JobRecord;
  const {view, error} = await loadJobResultView(job);
  state = {
    ...state,
    selectedJob: job,
    selectedResultView: view,
    resultViewError: error,
    actionMessage: `已读取任务详情：${job.job_id}`,
  };
  renderApp(state);
}

async function loadJobResultView(job: JobRecord): Promise<{
  view: JobResultView | null;
  error: string;
}> {
  if (!isResultViewAction(job.action_id) || job.status !== "succeeded") {
    return {view: null, error: ""};
  }
  const response = await fetch(`${apiBase}/api/jobs/${encodeURIComponent(job.job_id)}/result-view`);
  if (!response.ok) {
    return {view: null, error: await responseErrorMessage(response, "结果视图读取失败")};
  }
  return {view: (await response.json()) as JobResultView, error: ""};
}

async function startJob(
  actionId: string,
  parameters: Record<string, string | number | boolean>,
): Promise<void> {
  if (!state) return;
  state = {...state, pendingConfirmation: null, actionMessage: "任务已提交，等待后端开始执行。"};
  renderApp(state);

  const response = await fetch(`${apiBase}/api/jobs/${encodeURIComponent(actionId)}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({parameters}),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "任务提交失败"));
  }
  const job = (await response.json()) as JobRecord;
  state = {...state, selectedJob: job, selectedResultView: null, resultViewError: ""};
  await refreshJobs(`任务 ${job.label} 已启动：${job.job_id}`);
  pollJobs();
}

async function cancelJob(jobId: string): Promise<void> {
  if (!state || !jobId) return;
  state = {...state, actionMessage: `正在请求取消任务：${jobId}`};
  renderApp(state);

  const response = await fetch(`${apiBase}/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "任务取消失败"));
  }
  const job = (await response.json()) as JobRecord;
  state = {
    ...state,
    selectedJob: job,
    selectedResultView: null,
    resultViewError: "",
    actionMessage: `已请求取消任务：${job.job_id}`,
  };
  await refreshJobs();
  pollJobs();
}

async function confirmBacktestCandidate(jobId: string): Promise<void> {
  if (!state || !jobId) return;
  state = {...state, actionMessage: `正在确认候选回测：${jobId}`};
  renderApp(state);

  const response = await fetch(`${apiBase}/api/backtests/candidate`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({job_id: jobId}),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "候选回测确认失败"));
  }
  await response.json();
  state = state ? {...state, pendingCandidateConfirmation: null} : state;
  await refreshRuntimeState(`已确认候选回测：${jobId}`);
}

function prepareBacktestCandidateConfirmation(jobId: string): void {
  if (!state || !jobId) return;
  const item = state.backtestResults.results.find((result) => result.job_id === jobId);
  if (!item) {
    state = {...state, actionMessage: `未找到回测结果：${jobId}`};
    renderApp(state);
    return;
  }
  state = {
    ...state,
    pendingCandidateConfirmation: item,
    actionMessage: "请先核对候选质量门禁，再确认是否进入 Paper 准入。",
  };
  renderApp(state);
}

async function startRecommendedBacktest(scanJobId: string, runId: string): Promise<void> {
  if (!state || !scanJobId || !runId) return;
  state = {...state, actionMessage: `正在按扫描推荐提交回测：${runId}`};
  renderApp(state);
  await startJob("run_recommended_backtest", {
    scan_job_id: scanJobId,
    run_id: runId,
  });
}

async function recordReadinessDisposition(decisionId: string): Promise<void> {
  if (!state || !decisionId) return;
  state = {...state, actionMessage: `正在记录准入处置：${decisionId}`};
  renderApp(state);

  const response = await fetch(`${apiBase}/api/paper-readiness/disposition`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({decision_id: decisionId}),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "准入处置记录失败"));
  }
  const disposition = (await response.json()) as RecordedDisposition;
  await refreshRuntimeState(`已记录准入处置：${disposition.label}`);
  if (!state) return;
  const targetStepId = disposition.next_step_id;
  if (targetStepId && state.workflow.steps.some((step) => step.step_id === targetStepId)) {
    state = {...state, selectedStepId: targetStepId, actionMessage: `已记录准入处置：${disposition.label}`};
    renderApp(state);
  }
}

async function recordPaperObservationDisposition(decisionId: string): Promise<void> {
  if (!state || !decisionId) return;
  state = {...state, actionMessage: `正在记录 Paper 观察处置：${decisionId}`};
  renderApp(state);

  const response = await fetch(`${apiBase}/api/paper-observation/disposition`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({decision_id: decisionId}),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Paper 观察处置记录失败"));
  }
  const disposition = (await response.json()) as PaperObservationRecordedDisposition;
  await refreshRuntimeState(`已记录 Paper 观察处置：${disposition.label}`);
  if (!state) return;
  const targetStepId = disposition.next_step_id;
  if (targetStepId && state.workflow.steps.some((step) => step.step_id === targetStepId)) {
    state = {...state, selectedStepId: targetStepId, actionMessage: `已记录 Paper 观察处置：${disposition.label}`};
    renderApp(state);
  }
}

async function recordLiveReadinessDisposition(decisionId: string): Promise<void> {
  if (!state || !decisionId) return;
  state = {...state, actionMessage: `正在记录 Live 处置：${decisionId}`};
  renderApp(state);

  const response = await fetch(`${apiBase}/api/live-readiness/disposition`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({decision_id: decisionId}),
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "Live 处置记录失败"));
  }
  const disposition = (await response.json()) as LiveReadinessRecordedDisposition;
  await refreshRuntimeState(`已记录 Live 处置：${disposition.label}`);
  if (!state) return;
  const targetStepId = disposition.next_step_id;
  if (targetStepId && state.workflow.steps.some((step) => step.step_id === targetStepId)) {
    state = {...state, selectedStepId: targetStepId, actionMessage: `已记录 Live 处置：${disposition.label}`};
    renderApp(state);
  }
}

async function refreshJobs(message = ""): Promise<void> {
  await refreshRuntimeState(message);
}

function pollJobs(): void {
  const interval = window.setInterval(() => {
    if (!state) {
      window.clearInterval(interval);
      return;
    }
    const hasRunning = state.jobs.some((job) => isActiveJobStatus(job.status));
    if (!hasRunning) {
      window.clearInterval(interval);
      return;
    }
    refreshRuntimeState().then(() => {
      if (!state) return;
      const stillRunning = state.jobs.some((job) => isActiveJobStatus(job.status));
      if (!stillRunning) {
        const selectedJobId = state.selectedJob?.job_id ?? "";
        const selectedActionId = state.selectedJob?.action_id ?? "";
        state = {...state, actionMessage: "任务已完成，流程和产物已刷新。"};
        renderApp(state);
        window.clearInterval(interval);
        if (selectedJobId && isResultViewAction(selectedActionId)) {
          loadJobDetail(selectedJobId).catch(() => {
            // The job list is already refreshed; keep the current detail panel if the result view is unavailable.
          });
        }
      }
    }).catch(() => {
      window.clearInterval(interval);
    });
  }, 1500);
}

function collectActionParameters(actionId: string): Record<string, string | number | boolean> {
  const form = appRoot.querySelector<HTMLFormElement>(`[data-action-form="${actionId}"]`);
  if (!form) {
    return {};
  }
  const parameters: Record<string, string | number | boolean> = {};
  form
    .querySelectorAll<HTMLInputElement | HTMLSelectElement>("[data-param-name]")
    .forEach((input) => {
      const name = input.dataset.paramName;
      if (!name) return;
      if (input instanceof HTMLInputElement && input.type === "checkbox") {
        parameters[name] = input.checked;
        return;
      }
      parameters[name] = input.value;
    });
  return parameters;
}

function toggleBacktestComparison(jobId: string): void {
  if (!state || !jobId) return;
  const selected = state.selectedBacktestIds.includes(jobId);
  if (selected) {
    state = {
      ...state,
      selectedBacktestIds: state.selectedBacktestIds.filter((item) => item !== jobId),
      actionMessage: `已移出对比：${jobId}`,
    };
    renderApp(state);
    return;
  }
  if (state.selectedBacktestIds.length >= 5) {
    state = {...state, actionMessage: "最多同时对比 5 次回测。"};
    renderApp(state);
    return;
  }
  state = {
    ...state,
    selectedBacktestIds: [...state.selectedBacktestIds, jobId],
    actionMessage: `已加入对比：${jobId}`,
  };
  renderApp(state);
}

async function responseErrorMessage(response: Response, prefix: string): Promise<string> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      detail = payload.detail;
    }
  } catch {
    // Keep the HTTP status when the response is not JSON.
  }
  return `${prefix}：${detail}`;
}

function renderLoading(): void {
  const route = currentRoute();
  appRoot.innerHTML = `
    <section class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Quant System</p>
          <h1>${route === "workflow" ? "业务流程台" : "交易终端"}</h1>
        </div>
        <span class="badge neutral">loading</span>
      </header>
      <p class="muted">正在读取${route === "workflow" ? "流程状态" : "交易状态"}。</p>
    </section>
  `;
}

function renderError(message: string): void {
  const route = currentRoute();
  appRoot.innerHTML = `
    <section class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Quant System</p>
          <h1>${route === "workflow" ? "业务流程台" : "交易终端"}</h1>
        </div>
        <span class="badge danger">error</span>
      </header>
      <section class="panel">
        <h2>后端连接失败</h2>
        <p class="mono">${escapeHtml(message)}</p>
        <p class="muted">确认 FastAPI 服务运行在 ${escapeHtml(apiBase)}。</p>
      </section>
    </section>
  `;
}

function renderApp(current: AppState): void {
  const route = currentRoute();
  if (route === "terminal") {
    appRoot.innerHTML = `
      <section class="shell terminal-shell">
        <header class="topbar">
          <div>
            <p class="eyebrow">Quant System</p>
            <h1>交易终端</h1>
          </div>
          <div class="topbar-actions">
            <a class="page-link" href="${pageHref("workflow")}">流程台</a>
            <span class="badge ${terminalModeClass(current.tradingTerminal.mode.status)}">
              ${escapeHtml(current.tradingTerminal.mode.status)}
            </span>
          </div>
        </header>
        ${renderTradingTerminal(current)}
        ${renderArtifactViewer(current.artifact)}
        ${renderJobDetail(current.selectedJob, current.selectedResultView, current.resultViewError)}
      </section>
    `;
    return;
  }
  const step = selectedStep(current);
  appRoot.innerHTML = `
    <section class="shell">
      <header class="topbar">
        <div>
          <p class="eyebrow">Quant System</p>
          <h1>${escapeHtml(current.workflow.title)}</h1>
        </div>
        <div class="topbar-actions">
          <a class="page-link" href="${pageHref("terminal")}">交易终端</a>
          <span class="badge ${current.workflow.summary.next_live_decision.startsWith("NO_GO") ? "warning" : "success"}">
            ${escapeHtml(current.workflow.summary.next_live_decision)}
          </span>
        </div>
      </header>

      <section class="workflow-summary">
        ${summaryItem("策略", current.workflow.summary.strategy_id)}
        ${summaryItem("账户", current.workflow.summary.account_id || "-")}
        ${summaryItem("当前状态", current.workflow.summary.current_status)}
        ${summaryItem("下一步", current.workflow.summary.next_live_reason)}
        ${summaryItem("当前仓位", `${current.status.position.trading_pair} ${current.status.position.strategy_net_base_quantity}`)}
      </section>

      ${renderOperationGuide(current.operationGuide)}
      ${renderActiveJobs(current.jobs)}
      ${renderJobQueue(current.jobQueue)}
      ${renderStateDb(current.stateDb)}
      ${renderStrategyConfigPanel(current)}
      ${renderStrategyPortfolioPanel(current)}

      <section class="workflow-layout">
        <nav class="step-list" aria-label="业务流程阶段">
          ${current.workflow.steps.map((item, index) => renderStepButton(item, index + 1, current.selectedStepId)).join("")}
        </nav>

        <section class="step-detail">
          <div class="step-header">
            <div>
              <p class="eyebrow">${escapeHtml(step.phase)} · ${escapeHtml(step.owner)}</p>
              <h2>${escapeHtml(step.title)}</h2>
            </div>
            <span class="badge ${badgeClass(step.status)}">${escapeHtml(step.status)}</span>
          </div>

          <section class="business-goal">
            <strong>业务目标</strong>
            <p>${escapeHtml(step.business_goal)}</p>
          </section>

          <section class="decision-band">
            ${kv("门禁决策", step.decision)}
            ${kv("当前阶段", step.step_id === current.workflow.active_step_id ? "是" : "否")}
          </section>

          ${renderRuntimeAlerts(step.runtime_alerts)}

          <div class="detail-grid">
            <section class="panel compact">
              <h3>输入</h3>
              ${renderArtifacts(step.inputs)}
            </section>
            <section class="panel compact">
              <h3>输出</h3>
              ${renderArtifacts(step.outputs)}
            </section>
          </div>

          <section class="panel compact">
            <h3>阶段动作</h3>
            <div class="actions">
              ${step.actions.map((action) => renderAction(action, current.jobs)).join("")}
            </div>
            ${renderConfirmation(current, step)}
            ${current.actionMessage ? `<p class="action-message">${escapeHtml(current.actionMessage)}</p>` : ""}
          </section>

          ${renderReadinessDisposition(current, step)}
          ${renderPaperObservationDisposition(current, step)}
          ${renderHummingbotPaperStatus(current, step)}
          ${renderLiveReadinessPanel(current, step)}
          ${renderParameterScanRecommendations(current, step)}
          ${renderBacktestComparison(current, step)}

          ${step.notes.length ? `<section class="panel compact"><h3>备注</h3>${step.notes.map((note) => `<p class="muted">${escapeHtml(note)}</p>`).join("")}</section>` : ""}
        </section>
      </section>

      ${renderArtifactViewer(current.artifact)}
      ${renderJobDetail(current.selectedJob, current.selectedResultView, current.resultViewError)}

      <section class="panel full">
        <h2>最近任务</h2>
        ${renderJobs(current.jobs)}
      </section>
    </section>
  `;
}

function renderTradingTerminal(current: AppState): string {
  const terminal = current.tradingTerminal;
  const signal = terminal.strategy.signal_summary;
  const selectedPairs = Array.isArray(signal.selected_pairs) ? signal.selected_pairs.map(String).join(", ") : "";
  const latestSignal = typeof signal.latest_signal_timestamp === "string" ? signal.latest_signal_timestamp : "";
  return `
    <section class="terminal-status-band ${terminalModeClass(terminal.mode.status)}">
      <div>
        <p class="eyebrow">Terminal Mode</p>
        <h2>${escapeHtml(terminal.mode.label)}</h2>
        <p>${escapeHtml(terminal.mode.reason)}</p>
      </div>
      <div class="terminal-status-actions">
        <span class="badge ${terminalModeClass(terminal.mode.status)}">${escapeHtml(terminal.mode.next_live_decision || "unknown")}</span>
        <small>刷新时间 ${escapeHtml(shortTimestamp(terminal.generated_at))}</small>
      </div>
    </section>

    <section class="terminal-safety-grid">
      ${terminalFlag("Live Trading", terminal.safety.live_trading_enabled, true)}
      ${terminalFlag("Kill Switch", terminal.safety.global_kill_switch, false)}
      ${terminalFlag("Live Runner", terminal.safety.live_runner_exposed, true)}
      ${terminalFlag("Order Submit", terminal.safety.web_can_submit_live_order, true)}
      ${terminalFlag("Runner Disarmed", terminal.safety.runner_disarmed, true)}
      ${terminalFlag("Alert Channel", terminal.safety.alert_channel_configured, true)}
    </section>

    <section class="terminal-grid">
      <article class="panel terminal-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Account</p>
            <h2>账户与策略</h2>
          </div>
          <span class="badge neutral">${escapeHtml(terminal.account.connector || "connector")}</span>
        </div>
        <div class="terminal-kv-list">
          ${kv("账户", terminal.account.account_id)}
          ${kv("市场", terminal.account.market_type)}
          ${kv("策略", terminal.strategy.strategy_id)}
          ${kv("允许交易对", terminal.account.allowed_pairs.join(", "))}
          ${kv("选择交易对", selectedPairs)}
          ${kv("信号时间", shortTimestamp(latestSignal))}
        </div>
      </article>

      <article class="panel terminal-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Position</p>
            <h2>当前持仓</h2>
          </div>
          <span class="badge ${terminal.position.exit_requires_activation ? "warning" : "success"}">
            ${terminal.position.exit_requires_activation ? "exit approval" : "exit clear"}
          </span>
        </div>
        <div class="terminal-kv-list">
          ${kv("状态", terminal.position.stance)}
          ${kv("交易对", terminal.position.trading_pair)}
          ${kv("净持仓", terminal.position.strategy_net_base_quantity)}
          ${kv("账户余额", terminal.position.account_ending_base_balance)}
          ${kv("入场成本", terminal.position.entry_cost_basis_quote)}
          ${kv("入场均价", terminal.position.entry_average_price_quote)}
          ${kv("持有到", terminal.position.hold_until)}
        </div>
      </article>
    </section>

    <section class="panel terminal-card terminal-orders">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Candidate Orders</p>
          <h2>候选订单审批票据</h2>
        </div>
        <span class="badge ${terminal.candidate_orders.live_order_submission_armed ? "danger" : "neutral"}">
          ${terminal.candidate_orders.live_order_submission_armed ? "armed" : "not armed"}
        </span>
      </div>
      <p class="muted">${escapeHtml(terminal.candidate_orders.decision)}</p>
      ${renderTerminalOrders(terminal.candidate_orders.orders)}
      ${terminal.candidate_orders.checklist.length ? renderTerminalChecklist(terminal.candidate_orders.checklist) : ""}
    </section>

    <section class="terminal-grid">
      <article class="panel terminal-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Risk</p>
            <h2>风控限制</h2>
          </div>
          <span class="badge neutral">${escapeHtml(terminal.risk.allowed_pairs.join(", ") || "allowlist")}</span>
        </div>
        ${renderKeyValueEntries(terminal.risk.summary)}
        ${renderRiskChecks(terminal.risk.checks)}
      </article>

      <article class="panel terminal-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Execution</p>
            <h2>执行与对账</h2>
          </div>
          <span class="badge ${terminal.execution.status.includes("reconciled") ? "success" : "warning"}">
            ${escapeHtml(terminal.execution.status)}
          </span>
        </div>
        <div class="terminal-kv-list">
          ${kv("Expected", String(terminal.execution.order_checks.expected_orders ?? ""))}
          ${kv("Submitted", String(terminal.execution.order_checks.submitted_orders ?? ""))}
          ${kv("Filled", String(terminal.execution.order_checks.filled_orders ?? ""))}
          ${kv("DB fills", String(terminal.execution.order_checks.db_fills ?? ""))}
          ${kv("成交金额", terminal.execution.fill_summary.gross_quote_notional)}
          ${kv("净入账", terminal.execution.fill_summary.net_base_quantity)}
          ${kv("成交均价", terminal.execution.fill_summary.average_price_quote)}
          ${kv("Runner", terminal.execution.runner.live_order_submission_armed ? "armed" : "disarmed")}
        </div>
        ${renderOperationalChecks(terminal.execution.operational_checks)}
      </article>
    </section>

    <section class="terminal-grid">
      <article class="panel terminal-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Blockers</p>
            <h2>阻断与告警</h2>
          </div>
          <span class="badge ${terminal.blockers.some((item) => item.severity === "CRITICAL") ? "danger" : "warning"}">
            ${terminal.blockers.length}
          </span>
        </div>
        ${renderTerminalBlockers(terminal.blockers)}
      </article>

      <article class="panel terminal-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Actions</p>
            <h2>安全动作</h2>
          </div>
          <span class="badge neutral">review only</span>
        </div>
        ${renderTerminalActions(current)}
        ${renderTerminalConfirmation(current)}
        ${current.actionMessage ? `<p class="action-message">${escapeHtml(current.actionMessage)}</p>` : ""}
      </article>
    </section>

    ${renderActiveJobs(current.jobs)}

    <section class="panel full">
      <h2>最近任务</h2>
      ${renderJobs(current.jobs)}
    </section>
  `;
}

function terminalFlag(label: string, value: boolean, expectedTrue: boolean): string {
  const ok = value === expectedTrue;
  return `
    <div class="terminal-flag ${ok ? "ok" : "blocked"}">
      <span>${escapeHtml(label)}</span>
      <strong>${value ? "true" : "false"}</strong>
    </div>
  `;
}

function renderTerminalOrders(orders: TerminalCandidateOrder[]): string {
  if (!orders.length) {
    return `<p class="muted">暂无候选订单。</p>`;
  }
  return `
    <div class="terminal-order-list">
      ${orders
        .map(
          (order) => `
            <article class="terminal-order-ticket">
              <div>
                <span class="badge ${order.risk_checks.inside_allowlist ? "success" : "danger"}">
                  ${order.risk_checks.inside_allowlist ? "allowlist" : "blocked"}
                </span>
                <h3>${escapeHtml(order.side.toUpperCase())} ${escapeHtml(order.trading_pair)}</h3>
                <p class="muted">${escapeHtml(order.client_order_id)}</p>
              </div>
              <div class="terminal-ticket-grid">
                ${kv("类型", order.order_type)}
                ${kv("名义金额", order.notional_quote)}
                ${kv("估算价格", order.estimated_price)}
                ${kv("估算数量", order.estimated_quantity)}
                ${kv("信号时间", shortTimestamp(order.signal_timestamp))}
                ${kv("Momentum", order.signal_momentum)}
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTerminalChecklist(rows: {item_id: string; title: string; status: string; details: string}[]): string {
  return `
    <div class="terminal-checklist">
      ${rows
        .map(
          (row) => `
            <span>
              <strong>${escapeHtml(row.status)}</strong>
              ${escapeHtml(row.title)}
            </span>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderKeyValueEntries(entries: Record<string, string | number | boolean>): string {
  const rows = Object.entries(entries);
  if (!rows.length) {
    return `<p class="muted">暂无风控摘要。</p>`;
  }
  return `<div class="terminal-kv-list">${rows.map(([key, value]) => kv(key, String(value))).join("")}</div>`;
}

function renderRiskChecks(entries: Record<string, string | number | boolean | string[]>): string {
  const visible = Object.entries(entries).filter(([, value]) => typeof value === "boolean" || Array.isArray(value));
  if (!visible.length) {
    return "";
  }
  return `
    <div class="terminal-checklist">
      ${visible
        .map(([key, value]) => `<span><strong>${escapeHtml(key)}</strong>${escapeHtml(Array.isArray(value) ? value.join(", ") || "[]" : String(value))}</span>`)
        .join("")}
    </div>
  `;
}

function renderOperationalChecks(entries: Record<string, string | number | boolean>): string {
  const rows = Object.entries(entries);
  if (!rows.length) {
    return "";
  }
  return `<div class="terminal-checklist">${rows.map(([key, value]) => `<span><strong>${escapeHtml(key)}</strong>${escapeHtml(String(value))}</span>`).join("")}</div>`;
}

function renderTerminalBlockers(blockers: TerminalBlocker[]): string {
  if (!blockers.length) {
    return `<p class="muted">当前没有终端阻断项。</p>`;
  }
  return `
    <div class="terminal-blockers">
      ${blockers
        .map(
          (blocker) => `
            <article class="terminal-blocker ${terminalSeverityClass(blocker.severity)}">
              <span class="badge ${terminalSeverityClass(blocker.severity)}">${escapeHtml(blocker.severity)}</span>
              <div>
                <strong>${escapeHtml(blocker.title)}</strong>
                <p>${escapeHtml(blocker.message)}</p>
                <small>${escapeHtml(blocker.source)}</small>
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderTerminalActions(current: AppState): string {
  return `
    <div class="terminal-action-list">
      ${current.tradingTerminal.actions
        .map((action) => {
          const activeJob = activeJobForAction(current.jobs, action.action_id);
          return `
            <article class="terminal-action">
              <div>
                <strong>${escapeHtml(action.label)}</strong>
                <small>${escapeHtml(action.safety_level)} · ${escapeHtml(action.description)}</small>
                ${action.blocked_reason ? `<p class="blocked-note">${escapeHtml(action.blocked_reason)}</p>` : ""}
                ${activeJob ? `<p class="running-note">运行中：${escapeHtml(activeJob.job_id)}</p>` : ""}
              </div>
              <button
                class="action-submit"
                type="button"
                data-terminal-action-id="${escapeHtml(action.action_id)}"
                ${action.enabled && !activeJob ? "" : "disabled"}
              >
                ${action.enabled ? "准备执行" : "已阻断"}
              </button>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderTerminalConfirmation(current: AppState): string {
  const confirmation = current.pendingConfirmation;
  if (!confirmation || confirmation.stepId !== "terminal") {
    return "";
  }
  const action = current.tradingTerminal.actions.find((item) => item.action_id === confirmation.actionId);
  if (!action) {
    return "";
  }
  return `
    <section class="confirmation-panel terminal-confirmation">
      <h3>确认终端安全动作</h3>
      <p class="muted">${escapeHtml(action.description)}</p>
      <div class="decision-band">
        ${kv("action", action.action_id)}
        ${kv("safety", action.safety_level)}
      </div>
      <div class="confirmation-actions">
        <button class="action-submit" type="button" data-confirm-action-id="${escapeHtml(action.action_id)}">确认执行</button>
        <button class="secondary-button" type="button" data-cancel-confirm>取消</button>
      </div>
    </section>
  `;
}

function renderStepButton(step: WorkflowStep, index: number, selectedStepId: string): string {
  const selected = step.step_id === selectedStepId;
  const latestJob = latestStepJob(step);
  const runtimeClass = runtimeStatusClass(step.runtime_status);
  return `
    <button class="step-button ${selected ? "selected" : ""} ${latestJob ? "has-job" : ""} ${runtimeClass}" data-step-id="${escapeHtml(step.step_id)}">
      <span class="step-index">${index}</span>
      <span>
        <strong>${escapeHtml(step.title)}</strong>
        <small>${escapeHtml(step.phase)} · ${escapeHtml(step.decision)}</small>
        ${step.runtime_alerts.length ? `<small class="step-alert-line">${escapeHtml(step.runtime_alerts[0].title)} · ${escapeHtml(step.runtime_alerts[0].job_status)}</small>` : ""}
        ${latestJob ? `<small class="step-job-line">最近任务 · ${escapeHtml(latestJob.status)}</small>` : ""}
      </span>
      <span class="status-dot ${badgeClass(step.status)}"></span>
    </button>
  `;
}

function renderRuntimeAlerts(alerts: RuntimeAlert[]): string {
  if (!alerts.length) {
    return "";
  }
  return `
    <section class="runtime-alerts">
      <h3>运行告警</h3>
      ${alerts
        .map(
          (alert) => `
            <article class="runtime-alert ${alertSeverityClass(alert.severity)}">
              <span class="badge ${alertSeverityClass(alert.severity)}">${escapeHtml(alert.severity)}</span>
              <div>
                <strong>${escapeHtml(alert.title)}</strong>
                <p>${escapeHtml(alert.message)}</p>
                <button class="link-button" type="button" data-job-id="${escapeHtml(alert.job_id)}">查看任务详情</button>
              </div>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderArtifacts(artifacts: WorkflowArtifact[]): string {
  if (!artifacts.length) {
    return `<p class="muted">无。</p>`;
  }
  return `
    <ul class="artifact-list">
      ${artifacts
        .map(
          (artifact) => `
            <li>
              <span class="badge ${artifact.exists ? "success" : "danger"}">${artifact.exists ? "exists" : "missing"}</span>
              <div>
                <strong>${escapeHtml(artifact.label)}</strong>
                <small>${escapeHtml(artifact.kind)} · ${escapeHtml(artifact.path)}</small>
                <button class="link-button" data-artifact-path="${escapeHtml(artifact.path)}">查看</button>
              </div>
            </li>
          `,
        )
        .join("")}
    </ul>
  `;
}

function renderArtifactViewer(artifact: ArtifactContent | null): string {
  if (!artifact) {
    return "";
  }
  return `
    <section class="panel full artifact-viewer">
      <div class="artifact-viewer-title">
        <div>
          <h2>产物查看</h2>
          <p class="muted">${escapeHtml(artifact.path)} · ${escapeHtml(artifact.kind)} · ${artifact.size_bytes} bytes</p>
        </div>
        <span class="badge ${artifact.exists && !artifact.error ? "success" : "warning"}">
          ${artifact.exists ? (artifact.truncated ? "truncated" : "loaded") : "missing"}
        </span>
      </div>
      ${artifact.error ? `<p class="action-message">${escapeHtml(artifact.error)}</p>` : ""}
      ${artifact.content ? `<pre>${escapeHtml(artifact.content)}</pre>` : ""}
    </section>
  `;
}

function renderActiveJobs(jobs: JobRecord[]): string {
  const activeJobs = jobs.filter((job) => isActiveJobStatus(job.status));
  if (!activeJobs.length) {
    return "";
  }
  return `
    <section class="active-jobs">
      <div>
        <p class="eyebrow">运行中任务</p>
        <strong>${activeJobs.length} 个任务正在执行或等待结束</strong>
      </div>
      <div class="active-job-list">
        ${activeJobs
          .map(
            (job) => `
              <span>
                <span class="badge ${jobBadgeClass(job.status)}">${escapeHtml(job.status)}</span>
                ${escapeHtml(job.action_id)} · ${escapeHtml(job.job_id)}
                <button class="link-button" type="button" data-job-id="${escapeHtml(job.job_id)}">详情</button>
                <button class="link-button danger-link" type="button" data-cancel-job-id="${escapeHtml(job.job_id)}">取消</button>
              </span>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderJobQueue(queue: JobQueueState): string {
  const statusEntries = Object.entries(queue.status_counts);
  const activeEntries = Object.entries(queue.active_actions);
  return `
    <section class="panel compact">
      <div class="section-heading">
        <div>
          <p class="eyebrow">任务队列</p>
          <h2>持久化队列快照</h2>
        </div>
        <span class="badge ${queue.queue_persistence_enabled ? "success" : "warning"}">
          ${queue.queue_persistence_enabled ? "enabled" : "disabled"}
        </span>
      </div>
      <div class="decision-band">
        ${kv("队列文件", queue.path)}
        ${kv("总任务数", String(queue.total_jobs))}
        ${kv("活跃锁", String(activeEntries.length))}
        ${kv("更新时间", queue.last_updated_at)}
      </div>
      ${
        statusEntries.length
          ? `<div class="job-params">${statusEntries.map(([status, count]) => `<span>${escapeHtml(status)}=${count}</span>`).join("")}</div>`
          : `<p class="muted">暂无任务状态。</p>`
      }
      ${
        activeEntries.length
          ? `<div class="artifact-inline">${activeEntries.map(([actionId, jobId]) => `<span>${escapeHtml(actionId)}: ${escapeHtml(jobId)}</span>`).join("")}</div>`
          : `<p class="muted">当前没有运行中 action 锁。</p>`
      }
    </section>
  `;
}

function renderStateDb(stateDb: StateDbStatus): string {
  const recentDocuments = stateDb.documents.slice(0, 4);
  return `
    <section class="panel compact">
      <div class="section-heading">
        <div>
          <p class="eyebrow">状态数据库</p>
          <h2>SQLite 状态镜像</h2>
        </div>
        <span class="badge ${stateDb.database_ready ? "success" : "warning"}">
          ${stateDb.database_ready ? "ready" : "missing"}
        </span>
      </div>
      <div class="decision-band">
        ${kv("数据库", stateDb.path)}
        ${kv("状态文档", String(stateDb.document_count))}
        ${kv("审计事件", String(stateDb.audit_event_count))}
        ${kv("最近审计", stateDb.latest_audit_at || "-")}
      </div>
      ${
        recentDocuments.length
          ? `<div class="artifact-inline">${recentDocuments.map((item) => `<span>${escapeHtml(item.key)}: ${escapeHtml(item.source_path)}</span>`).join("")}</div>`
          : `<p class="muted">还没有镜像状态文档。</p>`
      }
    </section>
  `;
}

function renderOperationGuide(guide: OperationGuide): string {
  return `
    <section class="panel compact operation-guide">
      <div class="section-heading">
        <div>
          <p class="eyebrow">端到端向导</p>
          <h2>${escapeHtml(guide.current_step?.title ?? guide.title)}</h2>
        </div>
        <span class="badge ${guide.current_step ? "success" : "warning"}">
          ${escapeHtml(guide.current_step?.step_id ?? "unknown")}
        </span>
      </div>
      <div class="guide-steps">
        ${guide.steps.map(renderOperationGuideStep).join("")}
      </div>
      <div class="guide-notes">
        ${guide.safety_notes.map((note) => `<span>${escapeHtml(note)}</span>`).join("")}
      </div>
    </section>
  `;
}

function renderOperationGuideStep(step: OperationGuideStep): string {
  return `
    <button class="guide-step ${step.is_current ? "current" : ""}" type="button" data-step-id="${escapeHtml(step.step_id)}">
      <span>${step.order}</span>
      <strong>${escapeHtml(step.title)}</strong>
      <small>${escapeHtml(step.next_action_label)}</small>
      ${
        step.runtime_alert_count
          ? `<em>${step.runtime_alert_count} 个告警</em>`
          : step.blocked_actions.length
            ? `<em>${step.blocked_actions.length} 个阻断动作</em>`
            : ""
      }
    </button>
  `;
}

function renderStrategyConfigPanel(current: AppState): string {
  const selected = current.selectedStrategyConfig;
  return `
    <section class="panel compact">
      <div class="section-heading">
        <div>
          <p class="eyebrow">策略配置</p>
          <h2>在线编辑</h2>
        </div>
        <span class="badge neutral">${escapeHtml(current.strategyConfigs.backup_root)}</span>
      </div>
      <div class="config-grid">
        ${current.strategyConfigs.strategies.map(renderStrategyConfigSummary).join("")}
      </div>
      ${
        selected
          ? `
            <div class="config-editor">
              <div class="section-heading">
                <div>
                  <p class="eyebrow">${escapeHtml(selected.strategy_id)}</p>
                  <h3>${escapeHtml(selected.file_name)}</h3>
                </div>
                <button class="link-button" type="button" data-close-strategy-config>关闭</button>
              </div>
              <div class="decision-band">
                ${kv("路径", selected.path)}
                ${kv("大小", `${selected.size_bytes} bytes`)}
                ${kv("更新时间", selected.updated_at)}
                ${kv("sha256", selected.sha256.slice(0, 16))}
              </div>
              <textarea id="strategy-config-content" spellcheck="false">${escapeHtml(selected.content)}</textarea>
              <div class="form-actions">
                <button type="button" data-save-strategy-config>保存配置</button>
              </div>
            </div>
          `
          : `<p class="muted">选择一个策略配置文件后，可在页面中编辑并保存；保存前会自动备份。</p>`
      }
    </section>
  `;
}

function renderStrategyConfigSummary(strategy: StrategyConfigSummary): string {
  return `
    <article class="config-card">
      <strong>${escapeHtml(strategy.strategy_id)}</strong>
      <small>${escapeHtml(strategy.path)}</small>
      <div class="config-files">
        ${strategy.files
          .map(
            (file) => `
              <button
                class="link-button"
                type="button"
                data-config-strategy-id="${escapeHtml(strategy.strategy_id)}"
                data-config-file-name="${escapeHtml(file.file_name)}"
                ${file.exists ? "" : "disabled"}
              >
                ${escapeHtml(file.file_name)}
              </button>
            `,
          )
          .join("")}
      </div>
    </article>
  `;
}

function renderStrategyPortfolioPanel(current: AppState): string {
  const portfolio = current.strategyPortfolios.portfolios[0] ?? null;
  const memberByStrategy = new Map((portfolio?.members ?? []).map((member) => [member.strategy_id, member]));
  const defaultWeight =
    current.strategyPortfolios.supported_strategies.length > 0
      ? (1 / current.strategyPortfolios.supported_strategies.length).toFixed(4)
      : "1";
  return `
    <section class="panel compact">
      <div class="section-heading">
        <div>
          <p class="eyebrow">多策略组合</p>
          <h2>${escapeHtml(portfolio?.portfolio_id ?? "default_multi_strategy")}</h2>
        </div>
        <span class="badge neutral">${escapeHtml(current.strategyPortfolios.registry_path)}</span>
      </div>
      <div class="portfolio-grid">
        ${current.strategyPortfolios.supported_strategies
          .map((strategy) => {
            const member = memberByStrategy.get(strategy.strategy_id);
            const enabled = member?.enabled ?? true;
            const weight = member?.weight ?? defaultWeight;
            return `
              <label class="portfolio-row">
                <input
                  type="checkbox"
                  data-portfolio-enabled="${escapeHtml(strategy.strategy_id)}"
                  ${enabled ? "checked" : ""}
                />
                <span>
                  <strong>${escapeHtml(strategy.strategy_id)}</strong>
                  <small>${escapeHtml(strategy.path)}</small>
                </span>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.0001"
                  value="${escapeHtml(weight)}"
                  data-portfolio-weight="${escapeHtml(strategy.strategy_id)}"
                />
              </label>
            `;
          })
          .join("")}
      </div>
      <div class="decision-band">
        ${kv("当前总权重", portfolio?.total_weight ?? "-")}
        ${kv("更新时间", portfolio?.updated_at ?? "-")}
      </div>
      <div class="form-actions">
        <button type="button" data-save-strategy-portfolio>保存组合</button>
      </div>
    </section>
  `;
}

function renderJobDetail(
  job: JobRecord | null,
  resultView: JobResultView | null,
  resultViewError: string,
): string {
  if (!job) {
    return "";
  }
  return `
    <section class="panel full job-detail">
      <div class="job-detail-title">
        <div>
          <p class="eyebrow">任务详情</p>
          <h2>${escapeHtml(job.label)}</h2>
          <p class="muted">${escapeHtml(job.job_id)}</p>
        </div>
        <div class="job-detail-actions">
          <span class="badge ${jobBadgeClass(job.status)}">${escapeHtml(job.status)}</span>
          ${isActiveJobStatus(job.status) ? `<button class="secondary-button danger-button" type="button" data-cancel-job-id="${escapeHtml(job.job_id)}">取消任务</button>` : ""}
          <button class="secondary-button" type="button" data-close-job-detail>关闭</button>
        </div>
      </div>
      <section class="detail-grid">
        <div>
          ${kv("action", job.action_id)}
          ${kv("created", job.created_at)}
          ${kv("started", job.started_at || "-")}
          ${kv("completed", job.completed_at || "-")}
          ${kv("return code", job.return_code === null ? "-" : String(job.return_code))}
        </div>
        <div>
          ${Object.keys(job.parameters).length ? `<h3>运行参数</h3><div class="job-params">${Object.entries(job.parameters).map(([key, value]) => `<span>${escapeHtml(key)}=${escapeHtml(String(value))}</span>`).join("")}</div>` : "<p class=\"muted\">无运行参数。</p>"}
          ${Object.keys(job.artifacts).length ? `<h3>产物</h3><div class="artifact-inline">${Object.entries(job.artifacts).map(([key, value]) => `<span>${escapeHtml(key)}: ${escapeHtml(value)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(value)}">查看</button></span>`).join("")}</div>` : ""}
        </div>
      </section>
      ${renderResultSummary(job.result_summary)}
      ${renderJobResultView(job, resultView, resultViewError)}
      ${job.stdout ? `<h3>stdout</h3><pre class="job-log">${escapeHtml(job.stdout)}</pre>` : ""}
      ${job.stderr ? `<h3>stderr</h3><pre class="stderr job-log">${escapeHtml(job.stderr)}</pre>` : ""}
      ${job.error ? `<h3>error</h3><pre class="stderr job-log">${escapeHtml(job.error)}</pre>` : ""}
    </section>
  `;
}

function renderAction(action: WorkflowAction, jobs: JobRecord[]): string {
  if (action.action_type === "start_job") {
    const activeJob = activeJobForAction(jobs, action.action_id);
    const disabled = !action.enabled || activeJob !== null;
    return `
      <form class="action-card" data-action-form="${escapeHtml(action.action_id)}">
        <div class="action-card-header">
          <div>
            <strong>${escapeHtml(action.label)}</strong>
            <small>${escapeHtml(action.safety_level)} · ${escapeHtml(action.description)}</small>
            ${activeJob ? `<small class="running-note">已有运行中任务：${escapeHtml(activeJob.job_id)}</small>` : ""}
            ${!action.enabled && action.blocked_reason ? `<small class="blocked-note">${escapeHtml(action.blocked_reason)}</small>` : ""}
            ${action.runtime_alert ? `<small class="action-alert-note">${escapeHtml(action.runtime_alert.title)}：${escapeHtml(action.runtime_alert.job_status)}</small>` : ""}
          </div>
          <button class="action-submit" type="button" data-prepare-action-id="${escapeHtml(action.action_id)}" ${disabled ? "disabled" : ""}>
            ${activeJob ? "运行中" : "启动"}
          </button>
        </div>
        ${action.parameters.length ? `<div class="parameter-grid">${action.parameters.map((parameter) => renderParameter(action.action_id, parameter)).join("")}</div>` : ""}
        ${action.runtime_alert ? renderActionRuntimeAlert(action.runtime_alert) : ""}
        ${action.latest_job ? renderLatestActionJob(action.latest_job) : ""}
      </form>
    `;
  }
  return `
    <button class="action-button ${action.enabled ? "" : "disabled"}" data-action-id="${escapeHtml(action.action_id)}">
      <span>${escapeHtml(action.label)}</span>
      <small>${escapeHtml(action.safety_level)} · ${escapeHtml(action.description)}</small>
    </button>
  `;
}

function renderActionRuntimeAlert(alert: RuntimeAlert): string {
  return `
    <div class="action-runtime-alert ${alertSeverityClass(alert.severity)}">
      <strong>${escapeHtml(alert.title)}</strong>
      <span>${escapeHtml(alert.message)}</span>
    </div>
  `;
}

function renderConfirmation(current: AppState, step: WorkflowStep): string {
  const confirmation = current.pendingConfirmation;
  if (!confirmation || confirmation.stepId !== step.step_id) {
    return "";
  }
  const action = step.actions.find((item) => item.action_id === confirmation.actionId);
  if (!action) {
    return "";
  }
  const parameters = Object.entries(confirmation.parameters);
  return `
    <section class="confirm-panel">
      <div>
        <p class="eyebrow">启动确认</p>
        <h3>${escapeHtml(action.label)}</h3>
      </div>
      <div class="confirm-grid">
        ${kv("action", action.action_id)}
        ${kv("安全级别", action.safety_level)}
        ${kv("预计输出", action.output_dir_template || "reports/web_jobs/<generated-job-id>/")}
        ${kv("live 能力", "不开放")}
      </div>
      ${renderCandidateConfirmation(current, action)}
      ${parameters.length ? `<div class="job-params">${parameters.map(([key, value]) => `<span>${escapeHtml(key)}=${escapeHtml(String(value))}</span>`).join("")}</div>` : ""}
      <div class="confirm-actions">
        <button class="secondary-button" type="button" data-cancel-confirm>取消</button>
        <button class="action-submit" type="button" data-confirm-action-id="${escapeHtml(action.action_id)}">确认启动</button>
      </div>
    </section>
  `;
}

function renderCandidateConfirmation(current: AppState, action: WorkflowAction): string {
  if (action.action_id !== "generate_paper_readiness") {
    return "";
  }
  const candidate = current.backtestResults.candidate;
  if (!candidate) {
    return `<p class="action-message">需要先在研究阶段确认候选回测。</p>`;
  }
  return `
    <section class="candidate-confirmation">
      <strong>绑定候选回测</strong>
      <div class="confirm-grid">
        ${kv("candidate job", candidate.job_id)}
        ${kv("strategy", candidate.strategy_id)}
        ${kv("backtest json", candidate.artifact_path)}
        ${kv("selected at", candidate.selected_at)}
      </div>
      <div class="job-params">
        <span>total_return=${escapeHtml(formatMetricValue(candidate.metrics.total_return, "percent"))}</span>
        <span>max_drawdown=${escapeHtml(formatMetricValue(candidate.metrics.max_drawdown, "percent"))}</span>
        <span>tail_loss=${escapeHtml(formatMetricValue(candidate.metrics.tail_loss, "percent"))}</span>
      </div>
    </section>
  `;
}

function renderReadinessDisposition(current: AppState, step: WorkflowStep): string {
  if (step.step_id !== "paper_readiness") {
    return "";
  }
  const disposition = current.readinessDisposition;
  if (disposition.status === "not_available") {
    return `
      <section class="panel compact disposition-panel">
        <h3>准入处置</h3>
        <p class="muted">还没有 Web 生成的 Paper 准入报告。先确认候选回测并运行 Paper 准入。</p>
      </section>
    `;
  }
  const candidate = disposition.candidate;
  const criticalAlerts = disposition.alerts.filter((alert) => alert.severity === "CRITICAL");
  const warningAlerts = disposition.alerts.filter((alert) => alert.severity === "WARN");
  return `
    <section class="panel compact disposition-panel">
      <div class="disposition-title">
        <div>
          <h3>准入失败处置</h3>
          <p class="muted">
            ${escapeHtml(disposition.latest_job?.job_id ?? "-")}
            · ${escapeHtml(disposition.readiness_artifact || "-")}
          </p>
        </div>
        <span class="badge ${disposition.status === "blocked" ? "danger" : "success"}">${escapeHtml(disposition.status)}</span>
      </div>
      ${
        candidate
          ? `
            <section class="candidate-banner">
              <div>
                <strong>候选：${escapeHtml(shortJobId(candidate.job_id))}</strong>
                <p class="muted">${escapeHtml(candidate.strategy_id)} · ${escapeHtml(candidate.artifact_path)}</p>
              </div>
              <div class="candidate-metrics">
                <span>return ${escapeHtml(formatMetricValue(candidate.metrics?.total_return, "percent"))}</span>
                <span>drawdown ${escapeHtml(formatMetricValue(candidate.metrics?.max_drawdown, "percent"))}</span>
                <span>tail ${escapeHtml(formatMetricValue(candidate.metrics?.tail_loss, "percent"))}</span>
              </div>
            </section>
          `
          : `<p class="muted">当前准入报告没有绑定候选回测。</p>`
      }
      ${renderDispositionAlerts("CRITICAL", criticalAlerts)}
      ${renderDispositionAlerts("WARN", warningAlerts)}
      ${renderRepairGuidance(disposition.repair_guidance)}
      ${renderDispositionResolution(disposition.disposition_resolution)}
      ${renderDispositionOptions(disposition)}
      ${renderRecordedDisposition(disposition.recorded_disposition)}
    </section>
  `;
}

function renderPaperObservationDisposition(current: AppState, step: WorkflowStep): string {
  if (step.step_id !== "local_paper_observation") {
    return "";
  }
  const disposition = current.paperObservationDisposition;
  if (disposition.status === "not_available") {
    return `
      <section class="panel compact disposition-panel">
        <h3>Paper 观察处置</h3>
        <p class="muted">还没有 Web 运行的 Paper Smoke。先生成通过的 Paper 准入，再运行 Paper Smoke。</p>
      </section>
    `;
  }
  const badge = disposition.status === "ok" ? "success" : "warning";
  return `
    <section class="panel compact disposition-panel">
      <div class="disposition-title">
        <div>
          <h3>Paper 观察处置</h3>
          <p class="muted">
            ${escapeHtml(disposition.latest_job?.job_id ?? "-")}
            · ${escapeHtml(disposition.summary_artifact || "-")}
          </p>
        </div>
        <span class="badge ${badge}">${escapeHtml(disposition.status)}</span>
      </div>
      ${renderPaperObservationSummary(disposition)}
      ${renderDispositionAlerts("Paper Observation", disposition.alerts)}
      ${renderPaperObservationActions(disposition)}
      ${renderRecordedPaperObservationDisposition(disposition.recorded_disposition)}
    </section>
  `;
}

function renderPaperObservationSummary(disposition: PaperObservationDisposition): string {
  const metrics: ResultMetric[] = [
    {label: "cycles", value: disposition.summary.cycles || ""},
    {label: "ok_cycles", value: disposition.summary.ok_cycles || ""},
    {label: "failed_cycles", value: disposition.summary.failed_cycles || ""},
    {label: "routed_orders", value: disposition.summary.routed_orders || ""},
    {label: "approved_orders", value: disposition.summary.approved_orders || ""},
    {label: "rejected_orders", value: disposition.summary.rejected_orders || ""},
    {label: "last_equity", value: disposition.summary.last_equity || ""},
    {label: "max_drawdown", value: disposition.summary.max_drawdown || ""},
  ];
  const recommendations = disposition.recommended_actions.length
    ? `<div class="artifact-inline">${disposition.recommended_actions.map((action) => `<span>${escapeHtml(action)}</span>`).join("")}</div>`
    : "";
  return `
    <section class="result-summary">
      <h3>观察摘要</h3>
      ${renderResultMetrics(metrics)}
      ${recommendations}
      <div class="artifact-inline">
        ${disposition.observation_artifact ? `<span>observation_jsonl: ${escapeHtml(disposition.observation_artifact)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(disposition.observation_artifact)}">查看</button></span>` : ""}
        ${disposition.ledger_artifact ? `<span>ledger_jsonl: ${escapeHtml(disposition.ledger_artifact)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(disposition.ledger_artifact)}">查看</button></span>` : ""}
      </div>
    </section>
  `;
}

function renderPaperObservationActions(disposition: PaperObservationDisposition): string {
  if (!disposition.disposition_options.length) {
    return "";
  }
  return `
    <section class="disposition-options">
      <h3>处置动作</h3>
      <div class="disposition-actions">
        ${disposition.disposition_options
          .map(
            (option) => `
              <button
                class="disposition-action ${option.severity === "warning" ? "warning" : ""}"
                type="button"
                data-paper-observation-disposition-id="${escapeHtml(option.decision_id)}"
                ${option.enabled ? "" : "disabled"}
              >
                <strong>${escapeHtml(option.label)}</strong>
                <span>${escapeHtml(option.description)}</span>
              </button>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderRecordedPaperObservationDisposition(recorded: PaperObservationRecordedDisposition | null): string {
  if (!recorded) {
    return "";
  }
  return `
    <section class="recorded-disposition">
      <strong>最近 Paper 观察处置：${escapeHtml(recorded.label)}</strong>
      <p class="muted">
        ${escapeHtml(recorded.recorded_at)}
        · job ${escapeHtml(recorded.latest_observation_job_id || "-")}
        · status ${escapeHtml(recorded.observation_status || "-")}
        · next ${escapeHtml(recorded.next_step_id || "-")}
      </p>
    </section>
  `;
}

function renderHummingbotPaperStatus(current: AppState, step: WorkflowStep): string {
  if (step.step_id !== "hummingbot_paper") {
    return "";
  }
  const summary = current.hummingbotPaperStatus;
  const eventLog = summary.event_log;
  const badge = summary.status === "observing"
    ? "success"
    : summary.status === "not_started"
      ? "warning"
      : "default";
  const metrics: ResultMetric[] = [
    {label: "status", value: summary.status},
    {label: "state", value: String(summary.state.status || "-")},
    {label: "events", value: String(eventLog.line_count)},
    {label: "last_event", value: eventLog.last_event_type || "-"},
    {label: "last_timestamp", value: shortTimestamp(eventLog.last_timestamp || "")},
    {label: "parse_errors", value: String(eventLog.parse_errors)},
    {label: "started_by_web", value: String(summary.process_started_by_web)},
    {label: "live_orders", value: String(summary.live_order_submission_exposed)},
  ];
  return `
    <section class="panel compact disposition-panel">
      <div class="disposition-title">
        <div>
          <h3>Hummingbot Paper 运行监控</h3>
          <p class="muted">${escapeHtml(eventLog.path || "尚未记录 event log。")}</p>
        </div>
        <span class="badge ${badge}">${escapeHtml(summary.status)}</span>
      </div>
      ${renderResultMetrics(metrics)}
      <div class="artifact-inline">
        ${summary.state_exists ? `<span>session_state: ${escapeHtml(summary.state_path)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(summary.state_path)}">查看</button></span>` : "<span>session_state: missing</span>"}
        ${eventLog.exists ? `<span>event_log: ${escapeHtml(eventLog.path)}</span>` : "<span>event_log: missing</span>"}
      </div>
      ${summary.recommended_actions.length ? `<div class="artifact-inline">${summary.recommended_actions.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
    </section>
  `;
}

function renderLiveReadinessPanel(current: AppState, step: WorkflowStep): string {
  if (!["live_readiness", "first_live_batch", "cooldown_review"].includes(step.step_id)) {
    return "";
  }
  const summary = current.liveReadinessSummary;
  const metrics: ResultMetric[] = [
    {label: "status", value: summary.status},
    {label: "next_live", value: summary.next_live_decision || "-"},
    {label: "live_runner", value: String(summary.live_runner_exposed)},
    {label: "live_orders", value: String(summary.live_order_submission_exposed)},
    {label: "blockers", value: String(summary.blockers.length)},
    {label: "next_review", value: summary.next_review_not_before || "-"},
  ];
  return `
    <section class="panel compact disposition-panel">
      <div class="disposition-title">
        <div>
          <h3>Live 准入只读检查</h3>
          <p class="muted">${escapeHtml(summary.next_live_reason || "Live actions remain blocked in Web.")}</p>
        </div>
        <span class="badge ${summary.status === "blocked" ? "danger" : "warning"}">${escapeHtml(summary.status)}</span>
      </div>
      ${renderResultMetrics(metrics)}
      ${renderLiveReadinessReports(summary.reports)}
      ${renderLiveReadinessBlockers(summary.blockers)}
      ${renderLiveReadinessDispositionOptions(summary)}
      ${renderRecordedLiveReadinessDisposition(summary.recorded_disposition)}
      ${summary.recommended_actions.length ? `<div class="artifact-inline">${summary.recommended_actions.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
    </section>
  `;
}

function renderLiveReadinessReports(reports: LiveReadinessReport[]): string {
  const rows = reports.filter((report) => report.exists);
  if (!rows.length) {
    return `<p class="muted">未找到 live readiness 报告。</p>`;
  }
  return `
    <section class="trade-section">
      <div class="trade-title">
        <h3>Live 报告</h3>
        <span>${rows.length}</span>
      </div>
      <div class="table-scroll">
        <table class="trades-table paper-table">
          <thead>
            <tr>
              <th>报告</th>
              <th>决策</th>
              <th>告警</th>
              <th>生成时间</th>
              <th>产物</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (report) => `
                  <tr>
                    <td>${escapeHtml(report.label)}</td>
                    <td>${escapeHtml(report.decision || "-")}</td>
                    <td>${escapeHtml(`${report.critical_alerts}/${report.warning_alerts}/${report.alerts}`)}</td>
                    <td>${escapeHtml(shortTimestamp(report.generated_at))}</td>
                    <td><button class="link-button" type="button" data-artifact-path="${escapeHtml(report.path)}">查看</button></td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderLiveReadinessDispositionOptions(summary: LiveReadinessSummary): string {
  if (!summary.disposition_options.length) {
    return "";
  }
  return `
    <section class="disposition-options">
      <h3>Live 处置记录</h3>
      <div class="disposition-actions">
        ${summary.disposition_options
          .map(
            (option) => `
              <button
                class="disposition-action ${option.severity === "warning" ? "warning" : ""}"
                type="button"
                data-live-readiness-disposition-id="${escapeHtml(option.decision_id)}"
                ${option.enabled ? "" : "disabled"}
              >
                <strong>${escapeHtml(option.label)}</strong>
                <span>${escapeHtml(option.description)}</span>
              </button>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderRecordedLiveReadinessDisposition(recorded: LiveReadinessRecordedDisposition | null): string {
  if (!recorded) {
    return "";
  }
  return `
    <section class="recorded-disposition">
      <strong>最近 Live 处置：${escapeHtml(recorded.label)}</strong>
      <p class="muted">
        ${escapeHtml(recorded.recorded_at)}
        · decision ${escapeHtml(recorded.next_live_decision || "-")}
        · live_runner ${escapeHtml(String(recorded.live_runner_exposed))}
        · next ${escapeHtml(recorded.next_step_id || "-")}
      </p>
    </section>
  `;
}

function renderLiveReadinessBlockers(blockers: LiveReadinessBlocker[]): string {
  if (!blockers.length) {
    return "";
  }
  return `
    <section class="disposition-alerts">
      <h3>Live 阻断项</h3>
      ${blockers
        .map(
          (blocker) => `
            <article class="disposition-alert ${blocker.severity === "CRITICAL" ? "danger" : "warning"}">
              <span class="badge ${blocker.severity === "CRITICAL" ? "danger" : "warning"}">${escapeHtml(blocker.severity)}</span>
              <div>
                <strong>${escapeHtml(blocker.title)}</strong>
                <p>${escapeHtml(blocker.message)}</p>
              </div>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderDispositionResolution(resolution: DispositionResolution): string {
  if (!resolution || resolution.resolution_status === "none" || !resolution.message) {
    return "";
  }
  const badge = resolution.resolution_status === "superseded" ? "success" : "warning";
  return `
    <section class="disposition-resolution ${resolution.resolution_status}">
      <span class="badge ${badge}">${escapeHtml(resolution.resolution_status)}</span>
      <div>
        <strong>${escapeHtml(resolution.message)}</strong>
        <p class="muted">
          recorded ${escapeHtml(resolution.recorded_candidate_job_id || "-")}
          · current ${escapeHtml(resolution.current_candidate_job_id || "-")}
        </p>
      </div>
    </section>
  `;
}

function renderDispositionAlerts(title: string, alerts: ReadinessAlert[]): string {
  if (!alerts.length) {
    return "";
  }
  return `
    <section class="disposition-alerts">
      <h3>${escapeHtml(title)} 告警</h3>
      ${alerts
        .map(
          (alert) => `
            <article class="disposition-alert ${alert.severity === "CRITICAL" ? "danger" : "warning"}">
              <span class="badge ${alert.severity === "CRITICAL" ? "danger" : "warning"}">${escapeHtml(alert.severity)}</span>
              <div>
                <strong>${escapeHtml(alert.title)}</strong>
                <p>${escapeHtml(alert.message)}</p>
                <small>${escapeHtml(alert.hint)}</small>
              </div>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderRepairGuidance(guidance: ReadinessRepairGuidance[]): string {
  if (!guidance.length) {
    return "";
  }
  return `
    <section class="repair-guidance">
      <h3>证据修复引导</h3>
      <div class="repair-guidance-list">
        ${guidance
          .map(
            (item) => `
              <article class="repair-guidance-item ${item.severity === "warning" ? "warning" : ""}">
                <span class="badge ${item.severity === "warning" ? "warning" : "neutral"}">${escapeHtml(item.action_id)}</span>
                <div>
                  <strong>${escapeHtml(item.label)}</strong>
                  <p>${escapeHtml(item.description)}</p>
                  <button class="link-button" type="button" data-step-id="${escapeHtml(item.target_step_id)}" ${item.enabled ? "" : "disabled"}>
                    跳转阶段
                  </button>
                </div>
              </article>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderDispositionOptions(disposition: ReadinessDisposition): string {
  if (!disposition.disposition_options.length) {
    return "";
  }
  return `
    <section class="disposition-options">
      <h3>处置动作</h3>
      <div class="disposition-actions">
        ${disposition.disposition_options
          .map(
            (option) => `
              <button
                class="disposition-action ${option.severity === "warning" ? "warning" : ""}"
                type="button"
                data-readiness-disposition-id="${escapeHtml(option.decision_id)}"
                ${option.enabled ? "" : "disabled"}
              >
                <strong>${escapeHtml(option.label)}</strong>
                <span>${escapeHtml(option.description)}</span>
              </button>
            `,
          )
          .join("")}
      </div>
      <div class="artifact-inline">
        ${disposition.readiness_artifact ? `<span>readiness_json: ${escapeHtml(disposition.readiness_artifact)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(disposition.readiness_artifact)}">查看</button></span>` : ""}
        ${disposition.candidate?.job_id ? `<span>candidate_job: ${escapeHtml(disposition.candidate.job_id)} <button class="link-button" type="button" data-job-id="${escapeHtml(disposition.candidate.job_id)}">查看回测</button></span>` : ""}
      </div>
    </section>
  `;
}

function renderRecordedDisposition(recorded: RecordedDisposition | null): string {
  if (!recorded) {
    return "";
  }
  return `
    <section class="recorded-disposition">
      <strong>最近处置记录：${escapeHtml(recorded.label)}</strong>
      <p class="muted">
        ${escapeHtml(recorded.recorded_at)}
        · candidate ${escapeHtml(recorded.candidate_job_id || "-")}
        · status ${escapeHtml(recorded.resolution_status || "-")}
        · next ${escapeHtml(recorded.next_step_id || "-")}
      </p>
      ${recorded.message ? `<p class="muted">${escapeHtml(recorded.message)}</p>` : ""}
    </section>
  `;
}

function renderParameterScanRecommendations(current: AppState, step: WorkflowStep): string {
  if (step.step_id !== "research_backtest") {
    return "";
  }
  const latest = current.parameterScans.latest_scan;
  if (!latest) {
    return `
      <section class="panel compact scan-panel">
        <div class="backtest-results-title">
          <div>
            <h3>参数扫描推荐</h3>
            <p class="muted">运行参数扫描后，这里会显示按排序策略选出的候选参数组合。</p>
          </div>
          <span class="badge warning">scan_missing</span>
        </div>
      </section>
    `;
  }
  return `
    <section class="panel compact scan-panel">
      <div class="backtest-results-title">
        <div>
          <h3>参数扫描推荐</h3>
          <p class="muted">
            ${escapeHtml(shortJobId(latest.job_id))}
            · ${escapeHtml(latest.strategy_id)}
            · ${latest.run_count} runs
            · ${escapeHtml(latest.selection_policy.mode || "-")}
          </p>
        </div>
        <span class="badge ${latest.status === "succeeded" ? "success" : "warning"}">${escapeHtml(latest.status)}</span>
      </div>
      ${renderParameterScanBestRun(latest)}
      ${renderParameterScanTable(latest)}
      <div class="artifact-inline">
        ${latest.artifact_path ? `<span>scan_json: ${escapeHtml(latest.artifact_path)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(latest.artifact_path)}">查看</button></span>` : ""}
        ${latest.summary_csv_path ? `<span>summary_csv: ${escapeHtml(latest.summary_csv_path)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(latest.summary_csv_path)}">查看</button></span>` : ""}
      </div>
    </section>
  `;
}

function renderParameterScanBestRun(scan: ParameterScanItem): string {
  if (!scan.best_run) {
    return `<p class="muted">扫描结果中没有可推荐的参数组合。</p>`;
  }
  const run = scan.best_run;
  return `
    <section class="candidate-banner scan-best">
      <div>
        <strong>推荐组合：rank ${escapeHtml(String(run.rank))}</strong>
        <p class="muted">${escapeHtml(run.run_id)}</p>
      </div>
      <div class="candidate-metrics">
        <span>return ${escapeHtml(formatMetricValue(run.metrics.total_return, "percent"))}</span>
        <span>drawdown ${escapeHtml(formatMetricValue(run.metrics.max_drawdown, "percent"))}</span>
        <span>tail ${escapeHtml(formatMetricValue(run.metrics.tail_loss, "percent"))}</span>
        <span>trades ${escapeHtml(formatMetricValue(run.metrics.trade_count, "number"))}</span>
        <span>equiv ${escapeHtml(equivalenceLabel(run.equivalence))}</span>
      </div>
    </section>
  `;
}

function renderParameterScanTable(scan: ParameterScanItem): string {
  if (!scan.recommendations.length) {
    return `<p class="muted">暂无推荐行。</p>`;
  }
  return `
    <div class="table-scroll">
      <table class="backtest-results-table scan-results-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>组合</th>
            <th>参数</th>
            <th>收益</th>
            <th>最大回撤</th>
            <th>尾部亏损</th>
            <th>换手</th>
            <th>成交</th>
            <th>等价</th>
            <th>动作</th>
          </tr>
        </thead>
        <tbody>
          ${scan.recommendations
            .map(
              (run) => `
                <tr>
                  <td><span class="badge ${String(run.rank) === "1" ? "success" : "neutral"}">${escapeHtml(String(run.rank))}</span></td>
                  <td>
                    <strong>${escapeHtml(run.run_id)}</strong>
                    <small>${escapeHtml(run.recommendation)}</small>
                  </td>
                  <td>${renderScanParameterTags(run.parameters)}</td>
                  <td>${escapeHtml(formatMetricValue(run.metrics.total_return, "percent"))}</td>
                  <td>${escapeHtml(formatMetricValue(run.metrics.max_drawdown, "percent"))}</td>
                  <td>${escapeHtml(formatMetricValue(run.metrics.tail_loss, "percent"))}</td>
                  <td>${escapeHtml(formatMetricValue(run.metrics.turnover, "number"))}</td>
                  <td>${escapeHtml(formatMetricValue(run.metrics.trade_count, "number"))}</td>
                  <td>${renderEquivalenceBadge(run.equivalence)}</td>
                  <td>
                    <button
                      class="link-button"
                      type="button"
                      data-recommended-scan-job-id="${escapeHtml(scan.job_id)}"
                      data-recommended-run-id="${escapeHtml(run.run_id)}"
                    >
                      按推荐回测
                    </button>
                  </td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderScanParameterTags(parameters: Record<string, string>): string {
  const keys = [
    "fast_window",
    "slow_window",
    "lookback_window",
    "top_n",
    "min_momentum",
    "min_trend_strength",
    "max_volatility",
    "fee_rate",
    "slippage_bps",
  ];
  const tags = keys
    .filter((key) => parameters[key] !== undefined && parameters[key] !== "")
    .map((key) => `<span>${escapeHtml(key)}=${escapeHtml(parameters[key])}</span>`);
  return tags.length ? `<div class="scan-param-tags">${tags.join("")}</div>` : "-";
}

function renderBacktestComparison(current: AppState, step: WorkflowStep): string {
  if (step.step_id !== "research_backtest") {
    return "";
  }
  const results = current.backtestResults.results;
  const candidate = current.backtestResults.candidate;
  const selectedResults = results.filter((item) => current.selectedBacktestIds.includes(item.job_id));
  return `
    <section class="panel compact backtest-results-panel">
      <div class="backtest-results-title">
        <div>
          <h3>回测结果对比</h3>
          <p class="muted">从成功回测中选择 2-5 次横向比较，并确认进入后续 Paper 准入的候选。</p>
        </div>
        <span class="badge ${candidate ? "success" : "warning"}">${candidate ? "candidate_set" : "candidate_missing"}</span>
      </div>
      ${renderBacktestCandidate(candidate, current.backtestResults.candidate_path)}
      ${renderBacktestCandidateQualityConfirmation(current.pendingCandidateConfirmation)}
      ${renderBacktestResultsTable(results, current.selectedBacktestIds)}
      ${renderBacktestComparisonTable(selectedResults)}
    </section>
  `;
}

function renderBacktestCandidate(candidate: BacktestCandidate | null, candidatePath: string): string {
  if (!candidate) {
    return `<p class="muted">尚未确认候选回测。确认后会写入 ${escapeHtml(candidatePath)}。</p>`;
  }
  return `
    <section class="candidate-banner">
      <div>
        <strong>当前候选：${escapeHtml(shortJobId(candidate.job_id))}</strong>
        <p class="muted">
          ${escapeHtml(candidate.strategy_id)}
          · selected ${escapeHtml(candidate.selected_at)}
          · ${escapeHtml(candidatePath)}
        </p>
      </div>
      <div class="candidate-metrics">
        <span>return ${escapeHtml(formatMetricValue(candidate.metrics.total_return, "percent"))}</span>
        <span>drawdown ${escapeHtml(formatMetricValue(candidate.metrics.max_drawdown, "percent"))}</span>
        <span>trades ${escapeHtml(formatMetricValue(candidate.metrics.trade_count, "number"))}</span>
        <span>quality ${escapeHtml(candidate.quality_gate?.status ?? "-")}</span>
        <span>equiv ${escapeHtml(equivalenceLabel(candidate.equivalence))}</span>
      </div>
    </section>
  `;
}

function renderBacktestCandidateQualityConfirmation(item: BacktestResultItem | null): string {
  if (!item) {
    return "";
  }
  const quality = item.quality_gate;
  const warning = quality && quality.status !== "passed";
  return `
    <section class="candidate-quality-confirm ${warning ? "warning" : "passed"}">
      <div class="candidate-quality-title">
        <div>
          <p class="eyebrow">候选确认</p>
          <h3>${escapeHtml(shortJobId(item.job_id))}</h3>
          <p class="muted">${escapeHtml(item.strategy_id)} · ${escapeHtml(item.artifact_path)}</p>
        </div>
        <span class="badge ${warning ? "warning" : "success"}">${escapeHtml(quality?.status ?? "unknown")}</span>
      </div>
      ${quality ? `<p class="${warning ? "quality-warning" : "muted"}">${escapeHtml(quality.message)}</p>` : ""}
      ${renderEquivalenceNotice(item.equivalence)}
      ${renderCandidateQualityGateTable(quality)}
      <div class="confirm-actions">
        <button class="secondary-button" type="button" data-cancel-candidate-confirm>取消</button>
        <button class="action-submit ${warning ? "warning-submit" : ""}" type="button" data-confirm-candidate-id="${escapeHtml(item.job_id)}">
          ${warning ? "确认并记录风险" : "确认候选"}
        </button>
      </div>
    </section>
  `;
}

function renderCandidateQualityGateTable(quality: CandidateQualityGate | undefined): string {
  if (!quality?.gates?.length) {
    return `<p class="muted">没有候选质量门禁数据。</p>`;
  }
  return `
    <div class="table-scroll">
      <table class="quality-gate-table">
        <thead>
          <tr>
            <th>门禁</th>
            <th>观测值</th>
            <th>阈值</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          ${quality.gates
            .map(
              (gate) => `
                <tr>
                  <td>${escapeHtml(gate.label)}</td>
                  <td>${escapeHtml(formatMetricValue(gate.observed, gate.unit === "percent" ? "percent" : "number"))}</td>
                  <td>${escapeHtml(gate.operator)} ${escapeHtml(formatMetricValue(gate.threshold, gate.unit === "percent" ? "percent" : "number"))}</td>
                  <td><span class="badge ${gate.status === "passed" ? "success" : "warning"}">${escapeHtml(gate.status)}</span></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderEquivalenceNotice(equivalence: EquivalenceInfo | undefined): string {
  if (!equivalence || equivalence.status !== "equivalent") {
    return "";
  }
  const ids = equivalence.equivalent_ids.map(shortJobId).join(", ");
  return `
    <section class="equivalence-notice">
      <span class="badge warning">等价候选</span>
      <div>
        <strong>${escapeHtml(equivalence.message)}</strong>
        <p class="muted">${escapeHtml(ids)}</p>
      </div>
    </section>
  `;
}

function renderEquivalenceBadge(equivalence: EquivalenceInfo | undefined): string {
  if (!equivalence || equivalence.status === "unknown") {
    return `<span class="badge neutral">unknown</span>`;
  }
  if (equivalence.status === "equivalent") {
    return `<span class="badge warning">等价 x${equivalence.equivalent_count}</span>`;
  }
  return `<span class="badge success">unique</span>`;
}

function equivalenceLabel(equivalence: EquivalenceInfo | undefined): string {
  if (!equivalence) {
    return "-";
  }
  return equivalence.status === "equivalent" ? `x${equivalence.equivalent_count}` : equivalence.status;
}

function renderBacktestResultsTable(results: BacktestResultItem[], selectedBacktestIds: string[]): string {
  if (!results.length) {
    return `<p class="muted">暂无成功的 Web 回测任务。先运行一次回测后，这里会出现可对比记录。</p>`;
  }
  return `
    <div class="table-scroll">
      <table class="backtest-results-table">
        <thead>
          <tr>
            <th>对比</th>
            <th>任务</th>
            <th>策略</th>
            <th>窗口</th>
            <th>收益</th>
            <th>最大回撤</th>
            <th>尾部亏损</th>
            <th>换手</th>
            <th>成交</th>
            <th>质量</th>
            <th>等价</th>
            <th>动作</th>
          </tr>
        </thead>
        <tbody>
          ${results
            .slice(0, 12)
            .map((item) => {
              const selected = selectedBacktestIds.includes(item.job_id);
              return `
                <tr class="${item.selected_as_candidate ? "candidate-row" : ""}">
                  <td>
                    <button class="mini-button ${selected ? "selected" : ""}" type="button" data-toggle-backtest-id="${escapeHtml(item.job_id)}">
                      ${selected ? "移出" : "加入"}
                    </button>
                  </td>
                  <td>
                    <strong>${escapeHtml(shortJobId(item.job_id))}</strong>
                    <small>${escapeHtml(item.created_at)}</small>
                    ${item.selected_as_candidate ? `<small class="candidate-note">当前候选</small>` : ""}
                  </td>
                  <td>${escapeHtml(item.strategy_id)}</td>
                  <td>${escapeHtml(backtestWindow(item))}</td>
                  <td>${escapeHtml(formatMetricValue(item.metrics.total_return, "percent"))}</td>
                  <td>${escapeHtml(formatMetricValue(item.metrics.max_drawdown, "percent"))}</td>
                  <td>${escapeHtml(formatMetricValue(item.metrics.tail_loss, "percent"))}</td>
                  <td>${escapeHtml(formatMetricValue(item.metrics.turnover, "number"))}</td>
                  <td>${escapeHtml(formatMetricValue(item.metrics.trade_count, "number"))}</td>
                  <td><span class="badge ${item.quality_gate?.status === "passed" ? "success" : "warning"}">${escapeHtml(item.quality_gate?.status ?? "-")}</span></td>
                  <td>${renderEquivalenceBadge(item.equivalence)}</td>
                  <td>
                    <button class="link-button" type="button" data-job-id="${escapeHtml(item.job_id)}">详情</button>
                    <button class="link-button" type="button" data-prepare-backtest-candidate-id="${escapeHtml(item.job_id)}" ${item.selected_as_candidate ? "disabled" : ""}>设为候选</button>
                  </td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderBacktestComparisonTable(selectedResults: BacktestResultItem[]): string {
  if (selectedResults.length < 2) {
    return `<p class="muted">至少加入 2 次回测后显示横向对比。</p>`;
  }
  const rows: Array<[string, keyof BacktestResultItem["metrics"], "percent" | "number" | "text"]> = [
    ["总收益", "total_return", "percent"],
    ["最大回撤", "max_drawdown", "percent"],
    ["尾部亏损", "tail_loss", "percent"],
    ["换手", "turnover", "number"],
    ["成交数", "trade_count", "number"],
    ["结束权益", "end_equity", "number"],
    ["费用", "total_fees", "number"],
  ];
  return `
    <section class="comparison-matrix">
      <h3>已选对比</h3>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>指标</th>
              ${selectedResults.map((item) => `<th>${escapeHtml(shortJobId(item.job_id))}</th>`).join("")}
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                ([label, key, kind]) => `
                  <tr>
                    <td>${escapeHtml(label)}</td>
                    ${selectedResults
                      .map((item) => `<td>${escapeHtml(formatMetricValue(item.metrics[key], kind))}</td>`)
                      .join("")}
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderLatestActionJob(job: JobSummary): string {
  const artifacts = Object.entries(job.artifacts ?? {});
  return `
    <div class="action-run">
      <div class="action-run-title">
        <span class="badge ${jobBadgeClass(job.status)}">${escapeHtml(job.status)}</span>
        <div>
          <strong>最近执行</strong>
          <small>${escapeHtml(job.job_id)} · ${escapeHtml(job.created_at)}</small>
        </div>
      </div>
      ${Object.keys(job.parameters ?? {}).length ? `<div class="job-params">${Object.entries(job.parameters).map(([key, value]) => `<span>${escapeHtml(key)}=${escapeHtml(String(value))}</span>`).join("")}</div>` : ""}
      ${renderResultSummary(job.result_summary)}
      ${artifacts.length ? `<div class="artifact-inline">${artifacts.map(([key, value]) => `<span>${escapeHtml(key)}: ${escapeHtml(value)} <button class="link-button" type="button" data-artifact-path="${escapeHtml(value)}">查看</button></span>`).join("")}</div>` : ""}
      <button class="link-button" type="button" data-job-id="${escapeHtml(job.job_id)}">打开任务详情</button>
    </div>
  `;
}

function renderParameter(actionId: string, parameter: ActionParameter): string {
  const fieldId = `${actionId}-${parameter.name}`;
  const required = parameter.required ? "required" : "";
  const help = parameter.help ? `<small>${escapeHtml(parameter.help)}</small>` : "";
  if (parameter.input_type === "select") {
    return `
      <label class="parameter-field" for="${escapeHtml(fieldId)}">
        <span>${escapeHtml(parameter.label)}</span>
        <select id="${escapeHtml(fieldId)}" data-param-name="${escapeHtml(parameter.name)}" ${required}>
          ${parameter.options
            .map(
              (option) =>
                `<option value="${escapeHtml(option.value)}" ${option.value === String(parameter.default) ? "selected" : ""}>${escapeHtml(option.label)}</option>`,
            )
            .join("")}
        </select>
        ${help}
      </label>
    `;
  }
  if (parameter.input_type === "checkbox") {
    return `
      <label class="parameter-field checkbox-field" for="${escapeHtml(fieldId)}">
        <span>${escapeHtml(parameter.label)}</span>
        <input
          id="${escapeHtml(fieldId)}"
          type="checkbox"
          data-param-name="${escapeHtml(parameter.name)}"
          ${parameter.default ? "checked" : ""}
        />
        ${help}
      </label>
    `;
  }
  return `
    <label class="parameter-field" for="${escapeHtml(fieldId)}">
      <span>${escapeHtml(parameter.label)}</span>
      <input
        id="${escapeHtml(fieldId)}"
        type="${escapeHtml(parameter.input_type)}"
        data-param-name="${escapeHtml(parameter.name)}"
        value="${escapeHtml(String(parameter.default ?? ""))}"
        ${parameter.min ? `min="${escapeHtml(parameter.min)}"` : ""}
        ${parameter.max ? `max="${escapeHtml(parameter.max)}"` : ""}
        ${parameter.step ? `step="${escapeHtml(parameter.step)}"` : ""}
        ${required}
      />
      ${help}
    </label>
  `;
}

function renderResultSummary(summary: JobResultSummary | null | undefined, compact = false): string {
  if (!summary || !summary.metrics?.length) {
    return "";
  }
  const metrics = summary.metrics
    .filter((metric) => metric.value !== "")
    .slice(0, compact ? 5 : 12);
  if (!metrics.length) {
    return "";
  }
  return `
    <section class="result-summary ${compact ? "compact-summary" : ""}">
      <h3>${escapeHtml(summary.title || "结果摘要")}</h3>
      <div class="result-metrics">
        ${metrics
          .map(
            (metric) => `
              <div>
                <span>${escapeHtml(metric.label)}</span>
                <strong>${escapeHtml(metric.value)}</strong>
              </div>
            `,
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderResultMetrics(metrics: ResultMetric[]): string {
  const visible = metrics.filter((metric) => metric.value !== "").slice(0, 12);
  if (!visible.length) {
    return "";
  }
  return `
    <div class="result-metrics">
      ${visible.map((metric) => summaryItem(metric.label, metric.value)).join("")}
    </div>
  `;
}

function renderJobResultView(
  job: JobRecord,
  view: JobResultView | null,
  error: string,
): string {
  if (isBacktestJobAction(job.action_id)) {
    return renderBacktestResultView(job, view?.kind === "backtest" ? view : null, error);
  }
  if (job.action_id === "run_paper_smoke") {
    return renderPaperSmokeResultView(job, view?.kind === "paper_smoke" ? view : null, error);
  }
  if (job.action_id === "collect_hummingbot_paper_events") {
    return renderHummingbotEventsResultView(job, view?.kind === "hummingbot_events" ? view : null, error);
  }
  if (job.action_id === "run_hummingbot_export_acceptance") {
    return renderHummingbotAcceptanceResultView(job, view?.kind === "hummingbot_acceptance" ? view : null, error);
  }
  return "";
}

function renderBacktestResultView(
  job: JobRecord,
  view: BacktestResultView | null,
  error: string,
): string {
  if (!isBacktestJobAction(job.action_id)) {
    return "";
  }
  if (error) {
    return `
      <section class="result-visualization">
        <h3>回测可视化</h3>
        <p class="action-message">${escapeHtml(error)}</p>
      </section>
    `;
  }
  if (job.status !== "succeeded") {
    return `
      <section class="result-visualization">
        <h3>回测可视化</h3>
        <p class="muted">任务成功后生成权益曲线、回撤曲线和成交记录。</p>
      </section>
    `;
  }
  if (!view) {
    return `
      <section class="result-visualization">
        <h3>回测可视化</h3>
        <p class="muted">未找到可视化数据。</p>
      </section>
    `;
  }
  return `
    <section class="result-visualization">
      <div class="result-view-title">
        <div>
          <h3>回测可视化</h3>
          <p class="muted">${escapeHtml(view.strategy_id)} · ${escapeHtml(view.artifact_path)}</p>
        </div>
        <div class="result-view-counts">
          <span>${view.series_count} 个权益点${view.series_truncated ? " · 已抽样" : ""}</span>
          <span>${view.trade_count} 笔成交${view.trades_truncated ? " · 仅显示前 200 笔" : ""}</span>
        </div>
      </div>
      <div class="chart-grid">
        ${renderLineChart("权益曲线", view.series, "equity", formatNumberValue)}
        ${renderLineChart("回撤曲线", view.series, "drawdown", formatPercentValue)}
      </div>
      ${renderBacktestAnalysis(view)}
      ${renderBacktestTradeTable(view)}
    </section>
  `;
}

function renderBacktestAnalysis(view: BacktestResultView): string {
  const tradeStats = [
    ["成交数", view.trade_stats.trade_count ?? "0"],
    ["买入", view.trade_stats.buy_count ?? "0"],
    ["卖出", view.trade_stats.sell_count ?? "0"],
    ["标的数", view.trade_stats.symbol_count ?? "0"],
    ["总名义金额", view.trade_stats.gross_notional ?? "0"],
    ["平均名义金额", view.trade_stats.average_notional ?? "0"],
    ["手续费", view.trade_stats.fees ?? "0"],
  ];
  return `
    <section class="analysis-grid">
      <div class="analysis-card">
        <h3>成交统计</h3>
        <div class="result-metrics">
          ${tradeStats.map(([label, value]) => summaryItem(label, value)).join("")}
        </div>
      </div>
      <div class="analysis-card">
        <h3>月度收益</h3>
        ${renderMonthlyReturnTable(view.monthly_returns)}
      </div>
      <div class="analysis-card">
        <h3>回撤区间</h3>
        ${renderDrawdownEpisodeTable(view.drawdown_episodes)}
      </div>
    </section>
  `;
}

function renderMonthlyReturnTable(rows: BacktestMonthlyReturn[]): string {
  if (!rows.length) {
    return `<p class="muted">权益点不足，无法生成月度收益。</p>`;
  }
  return `
    <div class="table-scroll">
      <table class="trades-table compact-table">
        <thead>
          <tr>
            <th>月份</th>
            <th>期初</th>
            <th>期末</th>
            <th>收益</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .slice(-12)
            .map(
              (row) => `
                <tr>
                  <td>${escapeHtml(row.month)}</td>
                  <td>${escapeHtml(formatNumberValue(Number(row.start_equity)))}</td>
                  <td>${escapeHtml(formatNumberValue(Number(row.end_equity)))}</td>
                  <td>${escapeHtml(formatPercentValue(Number(row.return)))}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderDrawdownEpisodeTable(rows: BacktestDrawdownEpisode[]): string {
  if (!rows.length) {
    return `<p class="muted">没有检测到回撤区间。</p>`;
  }
  return `
    <div class="table-scroll">
      <table class="trades-table compact-table">
        <thead>
          <tr>
            <th>开始</th>
            <th>谷底</th>
            <th>恢复</th>
            <th>最大回撤</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  <td>${escapeHtml(shortTimestamp(row.start))}</td>
                  <td>${escapeHtml(shortTimestamp(row.trough))}</td>
                  <td>${escapeHtml(row.recovered_at ? shortTimestamp(row.recovered_at) : row.status)}</td>
                  <td>${escapeHtml(formatPercentValue(Number(row.trough_drawdown)))}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderPaperSmokeResultView(
  job: JobRecord,
  view: PaperSmokeResultView | null,
  error: string,
): string {
  if (job.action_id !== "run_paper_smoke") {
    return "";
  }
  if (error) {
    return `
      <section class="result-visualization">
        <h3>Paper Smoke 可视化</h3>
        <p class="action-message">${escapeHtml(error)}</p>
      </section>
    `;
  }
  if (job.status !== "succeeded") {
    return `
      <section class="result-visualization">
        <h3>Paper Smoke 可视化</h3>
        <p class="muted">任务成功后生成权益曲线、周期状态、订单审批和 ledger 成交记录。</p>
      </section>
    `;
  }
  if (!view) {
    return `
      <section class="result-visualization">
        <h3>Paper Smoke 可视化</h3>
        <p class="muted">未找到可视化数据。</p>
      </section>
    `;
  }
  return `
    <section class="result-visualization">
      <div class="result-view-title">
        <div>
          <h3>Paper Smoke 可视化</h3>
          <p class="muted">${escapeHtml(view.summary.status || "-")} · ${escapeHtml(view.artifact_path || "-")}</p>
        </div>
        <div class="result-view-counts">
          <span>${view.cycle_count} 个周期${view.cycles_truncated ? " · 仅显示前 100 个" : ""}</span>
          <span>${view.order_count} 个审批订单${view.orders_truncated ? " · 仅显示前 200 个" : ""}</span>
          <span>${view.ledger_order_count} 笔 ledger 成交${view.ledger_orders_truncated ? " · 仅显示前 200 笔" : ""}</span>
        </div>
      </div>
      ${renderResultMetrics(view.metrics)}
      <div class="chart-grid">
        ${renderLineChart("Paper 权益", view.series, "equity", formatNumberValue)}
        ${renderLineChart("Paper 回撤", view.series, "drawdown", formatPercentValue)}
      </div>
      ${renderPaperCycleTable(view)}
      ${renderPaperOrderTable(view)}
      ${renderPaperLedgerTable(view)}
    </section>
  `;
}

function renderHummingbotEventsResultView(
  job: JobRecord,
  view: HummingbotEventsResultView | null,
  error: string,
): string {
  if (job.action_id !== "collect_hummingbot_paper_events") {
    return "";
  }
  if (error) {
    return `
      <section class="result-visualization">
        <h3>Hummingbot 事件可视化</h3>
        <p class="action-message">${escapeHtml(error)}</p>
      </section>
    `;
  }
  if (!view) {
    return `
      <section class="result-visualization">
        <h3>Hummingbot 事件可视化</h3>
        <p class="muted">未找到事件可视化数据。</p>
      </section>
    `;
  }
  return `
    <section class="result-visualization">
      <div class="result-view-title">
        <div>
          <h3>Hummingbot 事件可视化</h3>
          <p class="muted">${escapeHtml(view.events_artifact_path || "-")}</p>
        </div>
        <div class="result-view-counts">
          <span>${view.event_count} 条事件${view.events_truncated ? " · 仅显示前 300 条" : ""}</span>
        </div>
      </div>
      ${renderResultMetrics(view.metrics)}
      ${renderHummingbotEventTypes(view.event_types)}
      ${renderHummingbotEventTable(view.events, view.event_count)}
    </section>
  `;
}

function renderHummingbotAcceptanceResultView(
  job: JobRecord,
  view: HummingbotAcceptanceResultView | null,
  error: string,
): string {
  if (job.action_id !== "run_hummingbot_export_acceptance") {
    return "";
  }
  if (error) {
    return `
      <section class="result-visualization">
        <h3>Hummingbot 验收可视化</h3>
        <p class="action-message">${escapeHtml(error)}</p>
      </section>
    `;
  }
  if (!view) {
    return `
      <section class="result-visualization">
        <h3>Hummingbot 验收可视化</h3>
        <p class="muted">未找到验收可视化数据。</p>
      </section>
    `;
  }
  return `
    <section class="result-visualization">
      <div class="result-view-title">
        <div>
          <h3>Hummingbot 验收可视化</h3>
          <p class="muted">${escapeHtml(view.artifact_path || "-")}</p>
        </div>
        <div class="result-view-counts">
          <span>${view.event_count} 条事件${view.events_truncated ? " · 仅显示前 300 条" : ""}</span>
        </div>
      </div>
      ${renderResultMetrics(view.metrics)}
      ${renderHummingbotEventTypes(view.event_types)}
      ${renderHummingbotEventTable(view.events, view.event_count)}
    </section>
  `;
}

function renderHummingbotEventTypes(rows: HummingbotEventTypeRow[]): string {
  if (!rows.length) {
    return "";
  }
  const maxCount = Math.max(...rows.map((row) => Number(row.count) || 0), 1);
  return `
    <section class="trade-section">
      <div class="trade-title">
        <h3>事件类型</h3>
        <span>${rows.length}</span>
      </div>
      <div class="result-metrics">
        ${rows.slice(0, 12).map((row) => summaryItem(row.event_type, `${row.count} · ${Math.round(((Number(row.count) || 0) / maxCount) * 100)}%`)).join("")}
      </div>
    </section>
  `;
}

function renderHummingbotEventTable(rows: HummingbotEventRow[], total: number): string {
  if (!rows.length) {
    return `
      <section class="trade-section">
        <h3>事件明细</h3>
        <p class="muted">没有可展示的 Hummingbot 事件。</p>
      </section>
    `;
  }
  return `
    <section class="trade-section">
      <div class="trade-title">
        <h3>事件明细</h3>
        <span>${rows.length} / ${total}</span>
      </div>
      <div class="table-scroll">
        <table class="trades-table paper-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>类型</th>
              <th>订单</th>
              <th>交易对</th>
              <th>方向</th>
              <th>状态</th>
              <th>价格</th>
              <th>数量</th>
            </tr>
          </thead>
          <tbody>
            ${rows.slice(0, 80).map((event) => `
              <tr>
                <td>${escapeHtml(shortTimestamp(event.timestamp))}</td>
                <td>${escapeHtml(event.event_type || "-")}</td>
                <td>${escapeHtml(event.client_order_id || "-")}</td>
                <td>${escapeHtml(event.trading_pair || "-")}</td>
                <td>${escapeHtml(event.side || "-")}</td>
                <td>${escapeHtml(event.status || "-")}</td>
                <td>${escapeHtml(event.price || "-")}</td>
                <td>${escapeHtml(event.amount || "-")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderLineChart(
  title: string,
  points: ResultSeriesPoint[],
  key: "equity" | "drawdown",
  formatter: (value: number) => string,
): string {
  const values = points.map((point) => point[key]).filter((value) => Number.isFinite(value));
  if (!values.length) {
    return `
      <article class="chart-card">
        <h3>${escapeHtml(title)}</h3>
        <p class="muted">无可用数据。</p>
      </article>
    `;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || Math.max(Math.abs(max), 1);
  const width = 640;
  const height = 190;
  const paddingX = 24;
  const paddingY = 18;
  const xSpan = width - paddingX * 2;
  const ySpan = height - paddingY * 2;
  const denominator = Math.max(points.length - 1, 1);
  const polyline = points
    .map((point, index) => {
      const value = Number.isFinite(point[key]) ? point[key] : min;
      const x = paddingX + (index / denominator) * xSpan;
      const y = height - paddingY - ((value - min) / range) * ySpan;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const firstTimestamp = points[0]?.timestamp ? points[0].timestamp.slice(0, 10) : "-";
  const lastTimestamp = points[points.length - 1]?.timestamp ? points[points.length - 1].timestamp.slice(0, 10) : "-";
  return `
    <article class="chart-card">
      <div class="chart-header">
        <h3>${escapeHtml(title)}</h3>
        <span>${escapeHtml(firstTimestamp)} - ${escapeHtml(lastTimestamp)}</span>
      </div>
      <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
        <line x1="${paddingX}" y1="${height - paddingY}" x2="${width - paddingX}" y2="${height - paddingY}" class="chart-axis-line"></line>
        <line x1="${paddingX}" y1="${paddingY}" x2="${paddingX}" y2="${height - paddingY}" class="chart-axis-line"></line>
        <polyline class="chart-line ${key === "drawdown" ? "drawdown-line" : "equity-line"}" points="${polyline}"></polyline>
      </svg>
      <div class="chart-scale">
        <span>${escapeHtml(formatter(min))}</span>
        <span>${escapeHtml(formatter(max))}</span>
      </div>
    </article>
  `;
}

function renderBacktestTradeTable(view: BacktestResultView): string {
  if (!view.trades.length) {
    return `
      <section class="trade-section">
        <h3>成交记录</h3>
        <p class="muted">本次回测没有成交。</p>
      </section>
    `;
  }
  const rows = view.trades.slice(0, 30);
  return `
    <section class="trade-section">
      <div class="trade-title">
        <h3>成交记录</h3>
        <span>${rows.length} / ${view.trade_count}</span>
      </div>
      <div class="table-scroll">
        <table class="trades-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>标的</th>
              <th>方向</th>
              <th>价格</th>
              <th>数量</th>
              <th>名义金额</th>
              <th>费用</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (trade) => `
                  <tr>
                    <td>${escapeHtml(shortTimestamp(trade.timestamp))}</td>
                    <td>${escapeHtml(trade.symbol)}</td>
                    <td><span class="side-badge ${trade.side === "sell" ? "sell" : "buy"}">${escapeHtml(trade.side || "-")}</span></td>
                    <td>${escapeHtml(trade.price)}</td>
                    <td>${escapeHtml(trade.quantity)}</td>
                    <td>${escapeHtml(trade.notional)}</td>
                    <td>${escapeHtml(trade.fee)}</td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderPaperCycleTable(view: PaperSmokeResultView): string {
  if (!view.cycles.length) {
    return `
      <section class="trade-section">
        <h3>观察周期</h3>
        <p class="muted">没有 observation 周期记录。</p>
      </section>
    `;
  }
  const rows = view.cycles.slice(0, 30);
  return `
    <section class="trade-section">
      <div class="trade-title">
        <h3>观察周期</h3>
        <span>${rows.length} / ${view.cycle_count}</span>
      </div>
      <div class="table-scroll">
        <table class="trades-table paper-table">
          <thead>
            <tr>
              <th>周期</th>
              <th>完成时间</th>
              <th>状态</th>
              <th>权益</th>
              <th>现金</th>
              <th>敞口</th>
              <th>订单</th>
              <th>数据完整</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (cycle) => `
                  <tr>
                    <td>${escapeHtml(cycle.cycle_number || "-")}</td>
                    <td>${escapeHtml(shortTimestamp(cycle.completed_at || cycle.started_at))}</td>
                    <td><span class="badge ${cycle.status === "ok" ? "success" : "danger"}">${escapeHtml(cycle.status || "-")}</span></td>
                    <td>${escapeHtml(cycle.equity || "-")}</td>
                    <td>${escapeHtml(cycle.cash || "-")}</td>
                    <td>${escapeHtml(cycle.gross_exposure || "-")}</td>
                    <td>${escapeHtml(`${cycle.approved_order_count || "0"}/${cycle.routed_order_count || "0"}`)}</td>
                    <td>${escapeHtml(cycle.market_data_complete || "-")}</td>
                    <td>${escapeHtml(cycle.error || "")}</td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderPaperOrderTable(view: PaperSmokeResultView): string {
  if (!view.orders.length) {
    return `
      <section class="trade-section">
        <h3>订单审批</h3>
        <p class="muted">本次 Paper Smoke 没有路由订单。</p>
      </section>
    `;
  }
  const rows = view.orders.slice(0, 50);
  return `
    <section class="trade-section">
      <div class="trade-title">
        <h3>订单审批</h3>
        <span>${rows.length} / ${view.order_count}</span>
      </div>
      <div class="table-scroll">
        <table class="trades-table paper-table">
          <thead>
            <tr>
              <th>周期</th>
              <th>时间</th>
              <th>intent</th>
              <th>审批</th>
              <th>原因</th>
              <th>外部订单</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (order) => `
                  <tr>
                    <td>${escapeHtml(order.cycle_number || "-")}</td>
                    <td>${escapeHtml(shortTimestamp(order.completed_at))}</td>
                    <td>${escapeHtml(order.intent_id || "-")}</td>
                    <td><span class="badge ${order.risk_status === "approved" ? "success" : "danger"}">${escapeHtml(order.risk_status || "-")}</span></td>
                    <td>${escapeHtml(order.risk_reason || "")}</td>
                    <td>${escapeHtml(order.external_order_id || "-")}</td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderPaperLedgerTable(view: PaperSmokeResultView): string {
  if (!view.ledger_orders.length) {
    return `
      <section class="trade-section">
        <h3>Ledger 成交</h3>
        <p class="muted">没有已写入 ledger 的成交。</p>
      </section>
    `;
  }
  const rows = view.ledger_orders.slice(0, 50);
  return `
    <section class="trade-section">
      <div class="trade-title">
        <h3>Ledger 成交</h3>
        <span>${rows.length} / ${view.ledger_order_count}</span>
      </div>
      <div class="table-scroll">
        <table class="trades-table paper-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>标的</th>
              <th>方向</th>
              <th>数量</th>
              <th>成交价</th>
              <th>名义金额</th>
              <th>费用</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            ${rows
              .map(
                (order) => `
                  <tr>
                    <td>${escapeHtml(shortTimestamp(order.created_at))}</td>
                    <td>${escapeHtml(order.symbol || "-")}</td>
                    <td><span class="side-badge ${order.side === "sell" ? "sell" : "buy"}">${escapeHtml(order.side || "-")}</span></td>
                    <td>${escapeHtml(order.quantity || "-")}</td>
                    <td>${escapeHtml(order.fill_price || "-")}</td>
                    <td>${escapeHtml(order.notional || "-")}</td>
                    <td>${escapeHtml(order.fee || "-")}</td>
                    <td>${escapeHtml(order.status || "-")}</td>
                  </tr>
                `,
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderJobs(jobs: JobRecord[]): string {
  if (!jobs.length) {
    return `<p class="muted">还没有从 Web 启动过任务。</p>`;
  }
  return `
    <div class="jobs">
      ${jobs.slice(0, 8).map(renderJob).join("")}
    </div>
  `;
}

function renderJob(job: JobRecord): string {
  return `
    <article class="job">
      <div class="job-title">
        <span class="badge ${jobBadgeClass(job.status)}">${escapeHtml(job.status)}</span>
        <div>
          <strong>${escapeHtml(job.label)}</strong>
          <small>${escapeHtml(job.job_id)}</small>
          <button class="link-button" type="button" data-job-id="${escapeHtml(job.job_id)}">详情</button>
        </div>
      </div>
      <div class="job-meta">
        ${kv("action", job.action_id)}
        ${kv("return code", job.return_code === null ? "-" : String(job.return_code))}
      </div>
      ${renderResultSummary(job.result_summary, true)}
      ${Object.keys(job.parameters).length ? `<div class="job-params">${Object.entries(job.parameters).map(([key, value]) => `<span>${escapeHtml(key)}=${escapeHtml(String(value))}</span>`).join("")}</div>` : ""}
      ${Object.keys(job.artifacts).length ? `<div class="artifact-inline">${Object.entries(job.artifacts).map(([key, value]) => `<span>${escapeHtml(key)}: ${escapeHtml(value)} <button class="link-button" data-artifact-path="${escapeHtml(value)}">查看</button></span>`).join("")}</div>` : ""}
      ${job.stdout ? `<pre>${escapeHtml(job.stdout)}</pre>` : ""}
      ${job.stderr ? `<pre class="stderr">${escapeHtml(job.stderr)}</pre>` : ""}
      ${job.error ? `<pre class="stderr">${escapeHtml(job.error)}</pre>` : ""}
    </article>
  `;
}

function selectedStep(current: AppState): WorkflowStep {
  return (
    current.workflow.steps.find((step) => step.step_id === current.selectedStepId) ??
    current.workflow.steps[0]
  );
}

function currentRoute(): "terminal" | "workflow" {
  const path = window.location.pathname.replace(/\/+$/, "");
  return path.endsWith("/workflow") ? "workflow" : "terminal";
}

function pageHref(page: "terminal" | "workflow"): string {
  const path = window.location.pathname.replace(/\/+$/, "");
  if (path.endsWith("/app")) {
    return page === "terminal" ? "/app/terminal" : "/app/workflow";
  }
  if (path.startsWith("/app/")) {
    return page === "terminal" ? "/app/terminal" : "/app/workflow";
  }
  return page === "terminal" ? "/terminal" : "/workflow";
}

function latestStepJob(step: WorkflowStep): JobSummary | null {
  const jobs = step.actions
    .map((action) => action.latest_job)
    .filter((job): job is JobSummary => job !== null);
  return jobs.sort((left, right) => right.created_at.localeCompare(left.created_at))[0] ?? null;
}

function activeJobForAction(jobs: JobRecord[], actionId: string): JobRecord | null {
  return jobs.find((job) => job.action_id === actionId && isActiveJobStatus(job.status)) ?? null;
}

function defaultBacktestSelection(payload: BacktestResultsPayload): string[] {
  const selected: string[] = [];
  if (payload.candidate?.job_id) {
    selected.push(payload.candidate.job_id);
  }
  for (const item of payload.results.slice(0, 2)) {
    if (!selected.includes(item.job_id)) {
      selected.push(item.job_id);
    }
  }
  return selected.slice(0, 5);
}

function isActiveJobStatus(status: string): boolean {
  return status === "queued" || status === "running" || status === "cancel_requested";
}

function isBacktestJobAction(actionId: string): boolean {
  return actionId === "run_backtest" || actionId === "run_recommended_backtest";
}

function isResultViewAction(actionId: string): boolean {
  return (
    isBacktestJobAction(actionId)
    || actionId === "run_paper_smoke"
    || actionId === "collect_hummingbot_paper_events"
    || actionId === "run_hummingbot_export_acceptance"
  );
}

function summaryItem(label: string, value: string): string {
  return `
    <div>
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "-")}</strong>
    </div>
  `;
}

function kv(label: string, value: string): string {
  return `
    <div class="kv">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "-")}</strong>
    </div>
  `;
}

function badgeClass(status: string): string {
  if (status === "completed") return "success";
  if (status === "active") return "warning";
  if (status === "attention_required") return "danger";
  return "neutral";
}

function terminalModeClass(status: string): string {
  if (status === "LIVE_BLOCKED") return "danger";
  if (status === "READY_FOR_MANUAL_REVIEW") return "warning";
  if (status === "PAPER_OBSERVING") return "success";
  return "neutral";
}

function terminalSeverityClass(severity: string): string {
  if (severity === "CRITICAL") return "danger";
  if (severity === "WARN") return "warning";
  return "neutral";
}

function runtimeStatusClass(status: string): string {
  if (status === "error") return "runtime-error";
  if (status === "warning") return "runtime-warning";
  return "";
}

function alertSeverityClass(severity: string): string {
  if (severity === "error") return "danger";
  if (severity === "warning") return "warning";
  return "neutral";
}

function jobBadgeClass(status: string): string {
  if (status === "succeeded") return "success";
  if (status === "failed" || status === "timed_out") return "danger";
  if (status === "running" || status === "queued" || status === "cancel_requested") return "warning";
  return "neutral";
}

function formatNumberValue(value: number): string {
  return numberFormatter.format(value);
}

function formatPercentValue(value: number): string {
  return percentFormatter.format(value);
}

function formatMetricValue(value: string | undefined, kind: "percent" | "number" | "text"): string {
  if (!value) {
    return "-";
  }
  const number = Number(value);
  if (Number.isFinite(number)) {
    if (kind === "percent") {
      return percentFormatter.format(number);
    }
    if (kind === "number") {
      return numberFormatter.format(number);
    }
  }
  return value;
}

function shortTimestamp(value: string): string {
  return value.replace("T", " ").replace("+00:00", "Z");
}

function shortJobId(jobId: string): string {
  const parts = jobId.split("_");
  if (parts.length >= 3) {
    return `${parts[0]}_${parts.at(-1)}`;
  }
  return jobId;
}

function backtestWindow(item: BacktestResultItem): string {
  const start = (item.parameters.start || "").slice(0, 10);
  const end = (item.parameters.end || "").slice(0, 10);
  if (!start && !end) {
    return "-";
  }
  return `${start || "?"} - ${end || "?"}`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function requireElement(element: HTMLDivElement | null): HTMLDivElement {
  if (!element) {
    throw new Error("missing #app root");
  }
  return element;
}
