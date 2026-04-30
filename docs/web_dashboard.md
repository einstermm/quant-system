# Web Dashboard

第一版 Web 提供业务流程展示、paper-safe 任务触发和只读产物查看，不暴露 live runner 或
live order submission。

## Backend

```bash
./venv/bin/python -m uvicorn apps.web_api.main:app --host 127.0.0.1 --port 8000
```

可用接口：

- `GET /`
- `GET /health`
- `GET /api/auth/status`
- `GET /api/audit`
- `GET /api/deployment/status`
- `GET /api/state-db/status`
- `GET /api/system/status`
- `GET /api/trading-terminal`
- `GET /api/strategy-configs`
- `GET /api/strategy-configs/{strategy_id}/{file_name}`
- `POST /api/strategy-configs/{strategy_id}/{file_name}`
- `GET /api/strategy-portfolios`
- `POST /api/strategy-portfolios`
- `GET /api/operation-guide`
- `GET /api/workflows/v0`
- `GET /api/jobs`
- `GET /api/jobs/queue`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/result-view`
- `GET /api/backtests/results`
- `GET /api/backtests/candidate`
- `POST /api/backtests/candidate`
- `GET /api/parameter-scans`
- `GET /api/paper-readiness/disposition`
- `POST /api/paper-readiness/disposition`
- `GET /api/hummingbot/paper-session/status`
- `GET /api/schedules`
- `POST /api/schedules`
- `POST /api/jobs/{action_id}`
- `POST /api/jobs/{job_id}/cancel`
- `GET /api/artifacts?path=<relative-path>`

当前允许的执行型 `action_id` 只有以下 paper-safe 任务，并支持参数化 POST body：

- `refresh_market_data`
- `query_strategy_data_quality`
- `run_backtest`
- `run_parameter_scan`
- `run_recommended_backtest`
- `run_candidate_walk_forward`
- `run_candidate_capacity_stress`
- `generate_paper_readiness`
- `run_paper_smoke`
- `generate_paper_observation_review`
- `run_hummingbot_sandbox_prepare`
- `run_hummingbot_runtime_preflight`
- `run_hummingbot_cli_direct_paper_handoff`
- `install_hummingbot_cli_direct_paper_files`
- `run_hummingbot_paper_session_control`
- `collect_hummingbot_paper_events`
- `run_hummingbot_export_acceptance`
- `run_hummingbot_observation_review`
- `generate_live_execution_package`
- `generate_live_post_trade_report`
- `generate_live_cooldown_review`
- `generate_live_initial_closure_report`
- `generate_live_position_exit_plan`
- `generate_external_alert_outbox`

示例：

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/run_backtest \
  -H 'Content-Type: application/json' \
  -d '{
    "parameters": {
      "strategy_id": "crypto_relative_strength_v1",
      "start": "2023-01-01",
      "end": "2026-01-01",
      "initial_equity": "10000"
    }
  }'
```

这些任务都会写入 `reports/web_jobs/<job_id>/`，并生成 `job.json` 记录本次运行参数、状态、
产物路径和 return code。Workflow API 会把每个动作最近一次 job 回挂到对应阶段动作上，前端
可直接查看该次运行的参数和产物。`GET /api/jobs/{job_id}` 会优先读取内存中的运行任务，
找不到时回退读取已经落盘的 `job.json`。Web 不支持 `run_live_batch`，也不暴露
任何 live runner 或 live order submission。

`generate_live_execution_package` 只生成 Live 执行申请包：

- 读取已审批的 activation plan、market data refresh 证据和 live risk 配置
- 输出 `live_execution_package_json`、`live_execution_package_md` 和 `candidate_orders_jsonl`
- 报告内固定标记 `execution_runner_generated=false`
- 报告内固定标记 `live_order_submission_armed=false`
- `run_live_batch` 仍在 Web 中保持 `blocked_live_action`

调度注册表：

- `GET /api/schedules` 读取 `reports/web_reviews/web_schedules.json`
- `POST /api/schedules` 可登记 safe action 的 interval、enabled 和 parameters
- 当前返回 `scheduler_worker_running=false`，表示 Web 只保存调度计划，常驻 worker 需要部署侧单独启动

权限：

- 默认开发环境未设置 `QUANT_WEB_API_KEY`，写接口不校验
- 部署时设置 `QUANT_WEB_API_KEY` 后，所有 POST 写操作必须带 `X-Quant-Api-Key`
- `GET /api/auth/status` 返回当前认证模式

审计：

- `GET /api/audit` 读取 `reports/web_reviews/audit_log.jsonl`
- 当前记录任务启动、任务取消、调度登记、候选回测确认、Paper 准入处置、Paper 观察处置和 Live 准入处置
- 审计事件包含 UTC 时间、事件类型、目标对象和写操作返回 payload，便于回溯页面上触发过的关键流程动作

部署：

- `GET /api/deployment/status` 返回当前 Web 部署形态、静态前端构建是否存在、Dockerfile/compose 是否就绪和认证模式
- 生产容器会把前端静态资源挂到 `/app`，API 根信息仍保留在 `/`
- 前端开发模式继续使用 Vite `5173` 端口；生产模式默认使用同源 API

同一个 `action_id` 同时只允许一个活跃任务。活跃状态包括 `queued`、`running` 和
`cancel_requested`。取消接口只对活跃任务有效，任务超时后会标记为 `timed_out`，后端重启后
发现落盘记录仍处于活跃状态时会在读取时标记为 `interrupted`。

任务队列：

- `GET /api/jobs/queue` 返回统一队列视图，并刷新 `reports/web_reviews/job_queue.json`
- 队列快照包含全部 Web job、状态计数、活跃 action 锁和每个 job 的 `job.json` 路径
- JobStore 会在任务进入 queued/running、取消和完成时自动更新队列快照
- API 重启后仍可从 `reports/web_jobs/*/job.json` 重建队列视图，未完成任务会标记为 `interrupted`

状态数据库：

- `GET /api/state-db/status` 返回 `data/web_state.sqlite` 的表、文档数量和审计事件数量
- SQLite 当前镜像关键状态文档：任务队列、调度、候选回测和三类处置记录
- 审计事件同时写入 `reports/web_reviews/audit_log.jsonl` 和 SQLite `audit_events`
- JSON/JSONL 仍是人工可读证据，SQLite 用于后续查询、索引和跨页面状态聚合

策略配置编辑：

- `GET /api/strategy-configs` 返回可编辑策略和白名单文件
- `GET /api/strategy-configs/{strategy_id}/{file_name}` 读取配置正文
- `POST /api/strategy-configs/{strategy_id}/{file_name}` 保存配置正文
- 仅允许编辑 `config.yml`、`risk.yml`、`backtest.yml` 和 `portfolio.yml`
- 保存前会备份到 `reports/web_reviews/strategy_config_backups/`
- `config.yml` 和 `backtest.yml` 必须保留匹配的 `strategy_id`

多策略组合：

- `GET /api/strategy-portfolios` 读取组合注册表和可用策略
- `POST /api/strategy-portfolios` 保存组合成员、权重和启用状态
- 权重只接受 0 到 1，小数最多保留 4 位，启用策略权重必须合计为 1
- 注册表写入 `reports/web_reviews/strategy_portfolios.json`，同时镜像到 SQLite 状态库

端到端操作向导：

- `GET /api/operation-guide` 从 Workflow API 派生顺序化操作向导
- 每个阶段返回当前状态、门禁决策、下一可执行动作、阻断动作和运行告警数量
- 页面用于告诉操作员“现在在哪一步、下一步点什么、哪里被阻断”

Workflow API 会把最近一次异常 job 反映到对应阶段：

- `failed`、`timed_out`、`interrupted` 生成 error 告警
- `canceled` 生成 warning 告警
- 有运行告警的阶段会返回 `runtime_alerts`，并把阶段 `status` 覆盖为 `attention_required`
- 原始阶段状态保留在 `base_status`

Job API 会根据已生成的产物动态返回 `result_summary`：

- `refresh_market_data`：策略、交易所、周期、交易对数量、刷新状态和写入 K 线数
- `query_strategy_data_quality`：策略所需 K 线查询数量、完整覆盖数量、质量通过数量和缺口数量
- `run_backtest`：策略、窗口、收益、回撤、尾部亏损、换手、交易数和结束权益
- `run_parameter_scan`：扫描次数、最佳组合、收益、回撤、尾部亏损、换手和交易数
- `run_recommended_backtest`：与普通回测相同，并记录来源扫描 job/run
- `run_candidate_walk_forward`：fold 数、正收益 fold 数、中位收益、最差收益、最差回撤和尾部亏损
- `run_candidate_capacity_stress`：使用高资金回测候选参数，摘要同普通回测
- `generate_paper_readiness`：准入状态、告警数量、关键阈值结果和容量摘要
- `run_paper_smoke`：cycle、订单、权益和回撤摘要
- `generate_paper_observation_review`：Paper 观察复盘决策、周期质量、收益回撤、拒单和行情完整性
- `run_hummingbot_sandbox_prepare`：Hummingbot paper/sandbox manifest、生命周期模拟和准备决策
- `run_hummingbot_runtime_preflight`：扫描 Hummingbot 挂载目录，检查 paper connector、live connector 和凭据字段风险
- `run_hummingbot_cli_direct_paper_handoff`：生成 Hummingbot CLI paper-mode 直连下单脚本和配置包
- `install_hummingbot_cli_direct_paper_files`：把 CLI paper 脚本和 script config 复制到 Hummingbot root
- `run_hummingbot_paper_session_control`：生成 Hummingbot paper 启停命令并记录人工启停状态
- `collect_hummingbot_paper_events`：从 session state/event JSONL 自动采集 Hummingbot paper 事件
- `run_hummingbot_export_acceptance`：验收 Hummingbot paper event JSONL，生成 reconciliation/session gate/package
- `run_hummingbot_observation_review`：基于 acceptance 和事件 JSONL 生成 Hummingbot paper 观察窗口复盘
- `generate_live_execution_package`：生成 live 候选订单申请包，但不生成 runner、不提交订单
- `generate_live_post_trade_report`：生成 live 成交后对账、日报和税务基础导出
- `generate_live_cooldown_review`：生成 live 冷却期复盘
- `generate_live_initial_closure_report`：生成初始闭环与仓位生命周期报告
- `generate_live_position_exit_plan`：生成真实仓位退出计划和审批清单，但不生成 runner、不提交订单
- `generate_external_alert_outbox`：生成标准化外部告警 payload/outbox；发送由独立 worker 处理

`GET /api/jobs/{job_id}/result-view` 当前支持 `run_backtest`、`run_recommended_backtest`、
`run_paper_smoke`、`collect_hummingbot_paper_events` 和 `run_hummingbot_export_acceptance` job。
回测 job 会读取 `backtest_json`，返回前端可直接渲染的结构化结果：

- `metrics`：回测核心指标
- `series`：权益序列，并按权益峰值计算每个点的 drawdown
- `trades`：成交明细，最多返回前 200 笔
- `series_count`、`trade_count` 和对应 truncated 标记

Paper Smoke job 会读取 `summary_json`、`observation_jsonl` 和 `ledger_jsonl`，返回：

- `metrics`：cycle、订单、权益、回撤和 market data 状态摘要
- `series`：Paper observation 权益序列和 drawdown
- `cycles`：每轮 observation 的权益、现金、敞口、订单计数和数据完整性
- `orders`：每个 routed order 的风控审批状态、原因和外部订单号
- `ledger_orders`：实际写入 paper ledger 的成交明细

Hummingbot event collection / export acceptance job 会返回：

- `metrics`：采集/验收决策、session、事件数量、解析错误和订单对账摘要
- `event_types`：按事件类型聚合的数量
- `events`：标准化后的关键事件行，包含时间、类型、订单、交易对、方向、状态、价格和数量

`GET /api/backtests/results` 汇总所有成功的 Web 回测任务，返回每次回测的参数、指标、
产物路径和候选状态。它同时包含普通回测和按扫描推荐生成的回测。`POST /api/backtests/candidate`
用于确认候选回测：

```bash
curl -X POST http://127.0.0.1:8000/api/backtests/candidate \
  -H 'Content-Type: application/json' \
  -d '{"job_id": "20260429T010544_run_backtest_4e60dce2"}'
```

确认结果会写入 `reports/web_reviews/backtest_candidate.json`。Workflow API 会读取该文件，
把研究阶段决策显示为 `backtest_candidate_confirmed`，并把候选回测作为 Paper 准入阶段的输入。

候选确认前会展示研究质量门禁，但不做硬阻断：

- 总收益必须非负
- 最大回撤不超过 20%
- 尾部亏损不超过 8%
- 换手不超过 45
- 成交数至少 1 笔

不达标的候选仍允许确认，但前端会要求在确认面板里看到风险提示，后端也会把
`quality_gate` 写入 `reports/web_reviews/backtest_candidate.json` 作为审计证据。

研究阶段也会识别等价候选。系统用核心指标
`total_return`、`max_drawdown`、`tail_loss`、`turnover`、`trade_count`、`end_equity`
组成等价键：

- 回测结果列表会标记 `unique`、`equivalent` 或 `unknown`
- 参数扫描推荐表会标记指标完全相同的推荐组合
- 如果某个候选与其他 job/run 的核心指标完全一致，确认面板会提示“等价候选”
- 等价候选不被硬阻断，但用于提醒操作员不要把重复结果误认为新的研究证据

研究阶段支持参数扫描与候选推荐：

- `run_parameter_scan` 调用 `packages.backtesting.run_parameter_scan`
- 扫描任务提供 `conservative`、`balanced`、`aggressive` 和 `custom` 模板，默认使用
  `balanced`
- `crypto_relative_strength_v1` 使用 `lookback_windows`、`rotation_top_n_values` 和
  `min_momentum` 扫描相对强弱轮动参数
- `crypto_momentum_v1` 使用 `fast_windows`、`slow_windows`、`min_trend_strengths` 和
  `max_volatility` 扫描均线/过滤参数
- 选择模板时，后端会按策略覆盖对应扫描范围；只有选择 `custom` 时才完全使用手动输入的范围
- Web 控制台限制单次扫描不超过 100 个组合
- `GET /api/parameter-scans` 返回最近扫描、最佳组合和前 8 个推荐组合
- 前端“参数扫描推荐”表可以点击“按推荐回测”，这会启动 `run_recommended_backtest`
- 推荐回测会把扫描 run 的参数传给 `packages.backtesting.run_backtest`，生成完整
  `backtest_json`；只有这种完整回测结果才能进一步“设为候选”
- 已确认候选后，研究阶段可以运行 `run_candidate_walk_forward`
- 该任务会读取 `reports/web_reviews/backtest_candidate.json` 和候选 `backtest_json`，把候选参数转成
  单组合 walk-forward 网格，并输出候选专属 `candidate_walk_forward.json`
- 已确认候选后，研究阶段也可以运行 `run_candidate_capacity_stress`
- 该任务会读取候选参数并使用高资金 `initial_equity` 运行压力回测，输出候选专属
  `candidate_capacity_stress.json`
- 后续 `generate_paper_readiness` 只使用当前候选最新的专属 walk-forward evidence 和
  capacity stress evidence，不再回退到策略级固定 evidence

Paper 准入任务现在强制引用已确认候选回测和候选专属 readiness evidence：

- 未确认候选前，`generate_paper_readiness` 动作不可启动
- 未生成当前候选的 `run_candidate_walk_forward` 前，`generate_paper_readiness` 动作不可启动
- 未生成当前候选的 `run_candidate_capacity_stress` 前，`generate_paper_readiness` 动作不可启动
- 启动时会把 `reports/web_reviews/backtest_candidate.json`、候选 `backtest_json` 和匹配策略的
  候选专属 walk-forward/capacity evidence 传给
  `packages.reporting.run_paper_readiness_report`
- 生成的 readiness JSON/Markdown 会包含 `candidate_backtest`
- 如果候选策略与 walk-forward readiness 策略不一致，报告会产生 CRITICAL 告警并进入 `blocked`
  状态，避免用错误证据推进 Paper

Paper Smoke 现在强制引用最新 Web 生成且通过的候选准入报告：

- 只接受 `paper_ready` 或 `paper_ready_with_warnings`
- 没有通过的 Web readiness 时，`run_paper_smoke` 动作不可启动
- 启动时会把最新通过的 `readiness_json` 传给 `packages.paper_trading.run_paper_observation`
- 页面可配置 paper 账户、初始资金、cycle 数、cycle 间隔、是否允许 readiness warning，以及是否在每个
  cycle 前刷新最近 Binance K 线
- 开启行情刷新时，可配置重叠 K 线数、初始化 K 线数和闭合延迟秒数
- 任务参数和产物会记录 `readiness_job_id`、`readiness_status` 和 `candidate_job_id`

`GET /api/paper-observation/disposition` 会读取最新 Web `run_paper_smoke` 任务，汇总本地 Paper
观察异常：

- job 未成功、cycle 失败、summary 缺失会形成 CRITICAL/WARN 告警
- 拒单会提示回到 Paper 准入复核风控限制和容量证据
- 行情不完整会提示开启行情刷新参数后重跑
- 页面可记录处置动作：按当前参数重跑、刷新行情后重跑、回到准入复核、暂停进入 Live
- 记录会落到 `reports/web_reviews/paper_observation_disposition.json`

`GET /api/live-readiness/summary` 是只读 Live 准入检查面板：

- 汇总 live readiness、activation checklist、connector preflight、first batch plan、post-trade、
  cooldown 和 initial closure 报告
- 显示每个报告的 decision/status、告警数量和产物入口
- 汇总当前 live 阻断项和 `next_live_decision`
- 明确返回 `live_runner_exposed=false`、`live_order_submission_exposed=false`
- `POST /api/live-readiness/disposition` 可记录保持阻断、等待 cooldown、复核 connector 或进入人工复核，
  记录落到 `reports/web_reviews/live_readiness_disposition.json`

`generate_paper_observation_review` 会使用最新成功的 Web Paper Smoke 产物生成复盘报告：

- 输入来自该 job 的 `observation_jsonl`、`ledger_jsonl` 和 `readiness_json`
- 初始资金继承 Paper Smoke job 参数
- 可在页面调整最小观察时长、OK cycle 比例和最大回撤阈值
- 输出 `paper_observation_review_json` 和 `paper_observation_review_md`
- 该复盘是后续 Hummingbot sandbox/paper 准备流程的 Web 输入

`run_hummingbot_sandbox_prepare` 会使用最新 Web Paper 观察复盘生成 Hummingbot sandbox 准备产物：

- 输入为 `paper_observation_review_json` 和对应 `ledger_jsonl`
- 可配置 paper connector、controller 名称和是否允许复盘 warning
- 输出 `sandbox_manifest_json`、`sandbox_prepare_json` 和 `sandbox_prepare_md`
- 只生成文件和模拟生命周期检查，不启动 Hummingbot，也不暴露 live connector/live order submission

`run_hummingbot_runtime_preflight` 会扫描本机 Hummingbot 配置挂载：

- `scan_roots` 支持逗号或换行分隔
- 输出 `runtime_preflight_json` 和 `runtime_preflight_md`
- 报告只记录字段名，不输出密钥值
- 若发现 live connector 或缺少期望的 paper connector，任务会失败并在流程中形成告警

`run_hummingbot_cli_direct_paper_handoff` 会读取最新 sandbox manifest 和 runtime preflight：

- 输出 `handoff_json`、`handoff_md`、`script_source` 和 `script_config`
- 可配置 Hummingbot root、容器内事件日志路径、script config 文件名和观察/心跳/余额快照间隔
- 产物包含 install target 路径，但该动作本身不安装、不启动 Hummingbot、不提交 live 订单
- 生成后可以继续运行 `install_hummingbot_cli_direct_paper_files`

`install_hummingbot_cli_direct_paper_files` 会读取最新 CLI Direct Paper Handoff：

- 自动复制 `script_source` 到 `<hummingbot_root>/scripts/`
- 自动复制 `script_config` 到 `<hummingbot_root>/conf/scripts/`
- 默认不覆盖已有不同内容；需要覆盖时在页面勾选 `允许覆盖`
- 可选清理同名旧事件 JSONL，避免新旧 paper session 混在一起
- 只做文件安装，不启动 Hummingbot、不连接交易所、不提交 live 订单

`run_hummingbot_paper_session_control` 会读取最新安装报告：

- `生成启动命令`：输出 docker/headless start command，不直接启动进程
- `记录已启动`：把人工启动状态写入 `reports/web_reviews/hummingbot_paper_session_state.json`
- `生成停止命令`：输出 `docker stop <container>` 命令
- `记录已停止`：把停止状态写入同一份 state JSON，后续可进入 export acceptance
- 输出 `session_control_json`、`session_control_md` 和 `session_state_json`

`GET /api/hummingbot/paper-session/status` 是 Hummingbot paper 只读监控接口：

- 读取 `hummingbot_paper_session_state.json`
- 检查记录的 event JSONL 是否存在、事件行数、最后事件类型和最后时间戳
- 返回 `not_started`、`started_no_events`、`observing` 或 `stopped_pending_acceptance`
- 明确返回 `process_started_by_web=false` 和 `live_order_submission_exposed=false`

`collect_hummingbot_paper_events` 会读取 session state 里的 `event_log_host_path`：

- 默认 `source_path=auto_from_session_state`
- 复制并标准化有效 JSONL 到 `reports/web_jobs/<job_id>/hummingbot_events/events.jsonl`
- 输出 `collection_report_json`、`collection_report_md` 和采集后的 `events_jsonl`
- 统计事件数量、事件类型、首尾时间戳、解析错误和截断状态
- `run_hummingbot_export_acceptance` 默认可使用最新采集的 `events_jsonl`

`run_hummingbot_export_acceptance` 会读取最新 Hummingbot sandbox prepare 产物和用户提供的
Hummingbot paper event JSONL：

- 支持 `hummingbot_export` 和 `replay` 两种事件来源
- 输出 `acceptance_json`、`reconciliation_json`、`session_gate_json` 和 `session_package_dir`
- 可选择允许 warning、跳过余额事件硬性要求，以及提供起始 quote 余额做余额对账
- 只读取事件文件并生成报告，不连接交易所、不提交订单

`run_hummingbot_observation_review` 会读取最新 export acceptance 和同一份事件 JSONL：

- 可配置目标观察窗口小时数和是否允许上游 warning
- 输出 `hummingbot_observation_review_json` 和 `hummingbot_observation_review_md`
- 用于判断是否可以延长 Hummingbot paper observation window

准入失败后，`GET /api/paper-readiness/disposition` 会读取最新 Web Paper 准入报告，返回：

- 最新 readiness job 和产物路径
- 绑定候选回测
- CRITICAL/WARN 告警及处置提示
- `repair_guidance`：根据失败原因给出下一步证据修复动作
- 可记录的处置方向：回到研究阶段更换候选、补齐容量压力证据、修复后重新生成准入

证据修复引导会区分失败类型：

- Walk-forward 稳定性问题会提示重新扫描参数或重跑候选 Walk-forward
- 容量问题会提示重跑候选 Capacity Stress
- 证据修复后再回到 Paper 准入门禁重新生成准入报告

`POST /api/paper-readiness/disposition` 会把操作员选择写入
`reports/web_reviews/paper_readiness_disposition.json`，仅作为流程审计记录，不会自动绕过风控或启动 live。

候选更换后会自动形成重新准入闭环：

- 处置记录会绑定当时失败的 `candidate_job_id`
- 如果最近处置是 `return_to_research` 且当前候选没有变化，`generate_paper_readiness` 会被禁用，
  后端也会拒绝重复生成准入
- 如果用户在研究阶段确认了新的候选，处置状态会返回 `superseded`，Paper 准入阶段会提示可以重新生成
- 历史处置文件不删除，API 会返回当前候选是否已覆盖旧处置

产物查看接口只接受仓库内相对路径，并限制在以下前缀：

- `docs/`
- `reports/`
- `strategies/`
- `data/reports/`
- `data/samples/`

交易终端聚合接口：

- `GET /api/trading-terminal` 返回前端默认交易终端所需的单一聚合 payload
- 数据来源包括 system status、Live readiness summary、Hummingbot paper status、Phase 6.5
  candidate package、Phase 6.7 post-trade report 和 Phase 6.9 initial closure report
- payload 固定返回 `live_runner_exposed=false`、`live_order_submission_exposed=false` 和
  `web_can_submit_live_order=false`
- `mode.status` 用于一屏提示当前操作状态：`LIVE_BLOCKED`、`LIVE_REVIEW_ONLY`、
  `PAPER_OBSERVING` 或 `READY_FOR_MANUAL_REVIEW`
- `candidate_orders` 只展示候选订单审批票据，包括交易对、方向、名义金额、估算价格、估算数量和
  allowlist / notional 风控摘要
- `blockers` 聚合 live disabled、kill switch、cooldown、runner disarm、readiness blocker、
  post-trade warning 和 initial closure warning
- `actions` 只列出安全动作：生成 Live 执行申请包、Post-trade 复盘、冷却复盘、初始闭环报告和仓位退出计划；
  `run_live_batch` 会显示为 disabled

## Frontend

```bash
cd apps/web_frontend
npm install
npm run dev
```

默认前端读取 `http://127.0.0.1:8000`。如需修改后端地址：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

前端提供两个独立页面：

- `/terminal`：交易终端；默认 `/` 也进入交易终端
- `/workflow`：流程台

- `交易终端` 用于查看账户、策略、持仓、候选订单、风控、阻断原因、执行对账和安全动作
- `流程台` 用于研究、回测、Paper、Hummingbot sandbox、Live 准入、报告、复盘和证据追溯
- 交易终端可启动的动作仍走 `POST /api/jobs/{action_id}`，并保留同 action 活跃任务保护
- 交易终端不提供实盘下单按钮；Live runner 和 live order submission 始终保持 Web 阻断

交易终端展示：

- 当前模式、下一次 live decision 和最后刷新时间
- `LIVE_TRADING_ENABLED`、`GLOBAL_KILL_SWITCH`、Live Runner、Order Submit、Runner Disarmed 和 Alert Channel
- 账户、connector、market type、策略、allowlist、selected pairs 和最新信号时间
- 当前持仓、净 BTC 数量、成本、入场均价、持仓计划和是否需要退出审批
- Phase 6.5 候选订单审批票据，不显示“立即下单”
- 风控限制、allowlist、cooldown 和阻断项
- Phase 6.7 执行与对账结果，包括 submitted/filled/db fills、成交金额、净入账和 runner 状态
- 安全动作入口：生成执行申请包、post-trade 复盘、冷却复盘、初始闭环报告和仓位退出计划

流程台展示：

- v0 当前版本定位
- 端到端业务流程阶段
- 每个阶段的业务目标、输入、输出、门禁决策和阶段动作
- 可安全执行的 paper-safe job 参数表单和状态
- 启动 paper-safe job 前的确认面板，显示 action、参数、安全级别和预计输出目录
- 运行中任务提示、同 action 重复提交保护和任务取消入口
- 失败、超时、取消、中断后的阶段级运行告警
- 每个阶段动作的最近一次执行记录、运行参数和产物入口
- 任务详情面板，集中查看状态、return code、stdout、stderr、运行参数和产物
- 任务结果摘要指标卡
- 回测任务详情中的权益曲线、回撤曲线和成交记录表
- 研究阶段的成功回测列表、2-5 次横向对比和候选回测确认
- 设为候选前的质量门禁确认面板，不达标时需要“确认并记录风险”
- 研究阶段的参数扫描启动表单、扫描推荐列表和按推荐回测入口
- 研究阶段的候选 Walk-forward 生成动作
- 研究阶段的候选 Capacity Stress 生成动作
- Paper 准入启动确认中的候选回测绑定信息
- Paper 准入 blocked 后的候选处置台、告警解释和处置记录
- 阶段产物和 job 产物的只读内容查看
- live 相关动作的阻断原因
