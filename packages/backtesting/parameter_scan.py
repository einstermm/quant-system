"""Parameter scan runner and experiment records."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import BacktestConfig, RegimeFilterBacktestConfig, SignalBacktestConfig
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.result import decimal_to_str


@dataclass(frozen=True, slots=True)
class ParameterGrid:
    fast_windows: tuple[int, ...]
    slow_windows: tuple[int, ...]
    fee_rates: tuple[Decimal, ...]
    slippage_bps_values: tuple[Decimal, ...]
    min_trend_strength_values: tuple[Decimal, ...] = field(default_factory=lambda: (Decimal("0"),))
    max_volatility_values: tuple[Decimal | None, ...] = field(default_factory=lambda: (None,))
    lookback_windows: tuple[int, ...] | None = None
    top_n_values: tuple[int, ...] | None = None
    min_momentum_values: tuple[Decimal, ...] = field(default_factory=lambda: (Decimal("0"),))

    def combinations(self) -> tuple["ParameterCombination", ...]:
        if self.lookback_windows is not None:
            return self._relative_strength_combinations()

        combinations: list[ParameterCombination] = []
        for fast_window in self.fast_windows:
            for slow_window in self.slow_windows:
                if fast_window >= slow_window:
                    continue
                for fee_rate in self.fee_rates:
                    for slippage_bps in self.slippage_bps_values:
                        for min_trend_strength in self.min_trend_strength_values:
                            for max_volatility in self.max_volatility_values:
                                combinations.append(
                                    ParameterCombination(
                                        fast_window=fast_window,
                                        slow_window=slow_window,
                                        fee_rate=fee_rate,
                                        slippage_bps=slippage_bps,
                                        min_trend_strength=min_trend_strength,
                                        max_volatility=max_volatility,
                                    )
                                )
        return tuple(combinations)

    def _relative_strength_combinations(self) -> tuple["ParameterCombination", ...]:
        combinations: list[ParameterCombination] = []
        for lookback_window in self.lookback_windows or ():
            for top_n in self.top_n_values or (None,):
                for fee_rate in self.fee_rates:
                    for slippage_bps in self.slippage_bps_values:
                        for min_momentum in self.min_momentum_values:
                            combinations.append(
                                ParameterCombination(
                                    fast_window=0,
                                    slow_window=0,
                                    fee_rate=fee_rate,
                                    slippage_bps=slippage_bps,
                                    lookback_window=lookback_window,
                                    top_n=top_n,
                                    min_momentum=min_momentum,
                                )
                            )
        return tuple(combinations)

    def to_dict(self) -> dict[str, object]:
        return {
            "fast_windows": list(self.fast_windows),
            "slow_windows": list(self.slow_windows),
            "fee_rates": [decimal_to_str(value) for value in self.fee_rates],
            "slippage_bps_values": [decimal_to_str(value) for value in self.slippage_bps_values],
            "min_trend_strength_values": [
                decimal_to_str(value) for value in self.min_trend_strength_values
            ],
            "max_volatility_values": [
                decimal_to_str(value) if value is not None else None
                for value in self.max_volatility_values
            ],
            "lookback_windows": list(self.lookback_windows) if self.lookback_windows is not None else None,
            "top_n_values": list(self.top_n_values) if self.top_n_values is not None else None,
            "min_momentum_values": [decimal_to_str(value) for value in self.min_momentum_values],
        }


@dataclass(frozen=True, slots=True)
class SelectionPolicy:
    mode: str = "return_first"
    min_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    max_turnover: Decimal | None = None
    max_tail_loss: Decimal | None = None
    drawdown_penalty: Decimal = Decimal("1")
    turnover_penalty: Decimal = Decimal("0.01")
    tail_loss_penalty: Decimal = Decimal("2")

    def __post_init__(self) -> None:
        if self.mode not in {"return_first", "risk_adjusted"}:
            raise ValueError(f"unsupported selection mode: {self.mode}")

    def ranking_key(self, metrics: dict[str, Decimal | int]) -> tuple[Decimal, ...]:
        total = _decimal_metric(metrics, "total_return")
        drawdown = _decimal_metric(metrics, "max_drawdown")
        turnover_value = _decimal_metric(metrics, "turnover")
        tail = _decimal_metric(metrics, "tail_loss")

        if self.mode == "return_first":
            return (-total, drawdown, turnover_value, tail)

        violation = self._constraint_violation(
            total_return=total,
            drawdown=drawdown,
            turnover_value=turnover_value,
            tail=tail,
        )
        score = (
            total
            - self.drawdown_penalty * drawdown
            - self.turnover_penalty * turnover_value
            - self.tail_loss_penalty * tail
        )
        return (
            Decimal("0") if violation == Decimal("0") else Decimal("1"),
            violation,
            -score,
            -total,
            drawdown,
            tail,
            turnover_value,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "min_return": decimal_to_str(self.min_return) if self.min_return is not None else None,
            "max_drawdown": decimal_to_str(self.max_drawdown)
            if self.max_drawdown is not None
            else None,
            "max_turnover": decimal_to_str(self.max_turnover)
            if self.max_turnover is not None
            else None,
            "max_tail_loss": decimal_to_str(self.max_tail_loss)
            if self.max_tail_loss is not None
            else None,
            "drawdown_penalty": decimal_to_str(self.drawdown_penalty),
            "turnover_penalty": decimal_to_str(self.turnover_penalty),
            "tail_loss_penalty": decimal_to_str(self.tail_loss_penalty),
        }

    def _constraint_violation(
        self,
        *,
        total_return: Decimal,
        drawdown: Decimal,
        turnover_value: Decimal,
        tail: Decimal,
    ) -> Decimal:
        violation = Decimal("0")
        if self.min_return is not None:
            violation += max(self.min_return - total_return, Decimal("0"))
        if self.max_drawdown is not None:
            violation += max(drawdown - self.max_drawdown, Decimal("0"))
        if self.max_turnover is not None:
            violation += max(turnover_value - self.max_turnover, Decimal("0"))
        if self.max_tail_loss is not None:
            violation += max(tail - self.max_tail_loss, Decimal("0"))
        return violation


@dataclass(frozen=True, slots=True)
class ParameterCombination:
    fast_window: int
    slow_window: int
    fee_rate: Decimal
    slippage_bps: Decimal
    min_trend_strength: Decimal = Decimal("0")
    max_volatility: Decimal | None = None
    lookback_window: int | None = None
    top_n: int | None = None
    min_momentum: Decimal = Decimal("0")

    @property
    def run_id(self) -> str:
        fee = decimal_to_str(self.fee_rate).replace(".", "p")
        slip = decimal_to_str(self.slippage_bps).replace(".", "p")
        if self.lookback_window is not None:
            momentum = decimal_to_str(self.min_momentum).replace(".", "p").replace("-", "m")
            top = f"_top_{self.top_n}" if self.top_n is not None else ""
            return f"lookback_{self.lookback_window}{top}_mom_{momentum}_fee_{fee}_slip_{slip}"

        run_id = f"fast_{self.fast_window}_slow_{self.slow_window}_fee_{fee}_slip_{slip}"
        if self.uses_regime_filter:
            trend = decimal_to_str(self.min_trend_strength).replace(".", "p")
            vol = "none" if self.max_volatility is None else decimal_to_str(self.max_volatility).replace(".", "p")
            run_id = f"{run_id}_trend_{trend}_vol_{vol}"
        return run_id

    @property
    def uses_regime_filter(self) -> bool:
        return self.min_trend_strength > Decimal("0") or self.max_volatility is not None

    def apply(self, config: BacktestConfig) -> BacktestConfig:
        regime_filter = config.regime_filter
        if self.uses_regime_filter:
            regime_filter = RegimeFilterBacktestConfig(
                enabled=True,
                min_trend_strength=self.min_trend_strength,
                max_volatility=self.max_volatility,
                volatility_window=config.regime_filter.volatility_window,
            )
        if config.signal.signal_type == "relative_strength_rotation":
            signal = SignalBacktestConfig(
                signal_type=config.signal.signal_type,
                fast_window=config.signal.fast_window,
                slow_window=config.signal.slow_window,
                lookback_window=self.lookback_window or config.signal.lookback_window,
                top_n=self.top_n or config.signal.top_n,
                min_momentum=self.min_momentum,
            )
        else:
            signal = SignalBacktestConfig(
                signal_type=config.signal.signal_type,
                fast_window=self.fast_window,
                slow_window=self.slow_window,
                lookback_window=config.signal.lookback_window,
                top_n=config.signal.top_n,
                min_momentum=config.signal.min_momentum,
            )

        return replace(
            config,
            fee_rate=self.fee_rate,
            slippage_bps=self.slippage_bps,
            signal=signal,
            regime_filter=regime_filter,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "fast_window": self.fast_window,
            "slow_window": self.slow_window,
            "fee_rate": decimal_to_str(self.fee_rate),
            "slippage_bps": decimal_to_str(self.slippage_bps),
            "min_trend_strength": decimal_to_str(self.min_trend_strength),
            "max_volatility": decimal_to_str(self.max_volatility)
            if self.max_volatility is not None
            else None,
            "lookback_window": self.lookback_window,
            "top_n": self.top_n,
            "min_momentum": decimal_to_str(self.min_momentum),
        }


@dataclass(frozen=True, slots=True)
class ScanRunSummary:
    rank: int
    run_id: str
    parameters: ParameterCombination
    metrics: dict[str, Decimal | int]

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "run_id": self.run_id,
            "parameters": self.parameters.to_dict(),
            "metrics": {
                key: decimal_to_str(value) if isinstance(value, Decimal) else value
                for key, value in self.metrics.items()
            },
        }


@dataclass(frozen=True, slots=True)
class ParameterScanResult:
    experiment_id: str
    strategy_id: str
    created_at: datetime
    code_version: str
    grid: ParameterGrid
    selection_policy: SelectionPolicy
    runs: tuple[ScanRunSummary, ...]

    @property
    def best_run(self) -> ScanRunSummary:
        if not self.runs:
            raise ValueError("scan result has no runs")
        return self.runs[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "created_at": self.created_at.isoformat(),
            "code_version": self.code_version,
            "grid": self.grid.to_dict(),
            "selection_policy": self.selection_policy.to_dict(),
            "best_run": self.best_run.to_dict(),
            "runs": [run.to_dict() for run in self.runs],
        }


class ParameterScanRunner:
    def __init__(self, engine: BacktestEngine, *, code_version: str = "unknown") -> None:
        self._engine = engine
        self._code_version = code_version

    def run(
        self,
        *,
        base_config: BacktestConfig,
        grid: ParameterGrid,
        experiment_id: str,
        selection_policy: SelectionPolicy | None = None,
    ) -> ParameterScanResult:
        policy = selection_policy or SelectionPolicy()
        raw_runs: list[tuple[ParameterCombination, dict[str, Decimal | int]]] = []
        for combination in grid.combinations():
            result = self._engine.run(combination.apply(base_config))
            raw_runs.append((combination, result.metrics))

        ranked = sorted(raw_runs, key=lambda item: policy.ranking_key(item[1]))
        runs = tuple(
            ScanRunSummary(
                rank=index + 1,
                run_id=combination.run_id,
                parameters=combination,
                metrics=metrics,
            )
            for index, (combination, metrics) in enumerate(ranked)
        )
        return ParameterScanResult(
            experiment_id=experiment_id,
            strategy_id=base_config.strategy_id,
            created_at=datetime.now(tz=UTC),
            code_version=self._code_version,
            grid=grid,
            selection_policy=policy,
            runs=runs,
        )


def write_parameter_scan_json(scan_result: ParameterScanResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(scan_result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_parameter_scan_csv(scan_result: ParameterScanResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "rank",
        "run_id",
        "fast_window",
        "slow_window",
        "fee_rate",
        "slippage_bps",
        "min_trend_strength",
        "max_volatility",
        "lookback_window",
        "top_n",
        "min_momentum",
        "total_return",
        "max_drawdown",
        "tail_loss",
        "end_equity",
        "turnover",
        "total_fees",
        "trade_count",
    )

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for run in scan_result.runs:
            row = {
                "rank": run.rank,
                "run_id": run.run_id,
                **run.parameters.to_dict(),
            }
            for key in fieldnames:
                if key in row:
                    continue
                value = run.metrics[key]
                row[key] = decimal_to_str(value) if isinstance(value, Decimal) else value
            writer.writerow(row)

    return output_path


def _decimal_metric(metrics: dict[str, Decimal | int], key: str) -> Decimal:
    value = metrics[key]
    if isinstance(value, Decimal):
        return value
    return Decimal(value)
