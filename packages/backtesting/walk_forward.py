"""Walk-forward robustness validation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from packages.backtesting.config import BacktestConfig
from packages.backtesting.engine import BacktestEngine
from packages.backtesting.parameter_scan import (
    ParameterCombination,
    ParameterGrid,
    SelectionPolicy,
    _decimal_metric,
)
from packages.backtesting.result import decimal_to_str
from packages.backtesting.train_test_validation import TrainTestRunSummary, TrainTestSplit


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_id: int
    split: TrainTestSplit

    def to_dict(self) -> dict[str, object]:
        return {
            "fold_id": self.fold_id,
            **self.split.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class WalkForwardFoldResult:
    fold: WalkForwardFold
    selected_run: TrainTestRunSummary
    best_test_run: TrainTestRunSummary
    runs: tuple[TrainTestRunSummary, ...]

    @property
    def selected_test_return(self) -> Decimal:
        return _decimal_metric(self.selected_run.test_metrics, "total_return")

    @property
    def selected_test_drawdown(self) -> Decimal:
        return _decimal_metric(self.selected_run.test_metrics, "max_drawdown")

    @property
    def selected_test_tail_loss(self) -> Decimal:
        return _decimal_metric(self.selected_run.test_metrics, "tail_loss")

    @property
    def selected_test_positive(self) -> bool:
        return self.selected_test_return > Decimal("0")

    def to_dict(self) -> dict[str, object]:
        return {
            "fold": self.fold.to_dict(),
            "selected_run": self.selected_run.to_dict(),
            "best_test_run": self.best_test_run.to_dict(),
            "runs": [run.to_dict() for run in self.runs],
        }


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    experiment_id: str
    strategy_id: str
    created_at: datetime
    code_version: str
    grid: ParameterGrid
    selection_policy: SelectionPolicy
    folds: tuple[WalkForwardFoldResult, ...]

    @property
    def selected_positive_folds(self) -> int:
        return sum(1 for fold in self.folds if fold.selected_test_positive)

    @property
    def average_selected_test_return(self) -> Decimal:
        if not self.folds:
            raise ValueError("walk-forward result has no folds")
        return sum((fold.selected_test_return for fold in self.folds), Decimal("0")) / Decimal(
            len(self.folds)
        )

    @property
    def median_selected_test_return(self) -> Decimal:
        if not self.folds:
            raise ValueError("walk-forward result has no folds")
        values = sorted(fold.selected_test_return for fold in self.folds)
        midpoint = len(values) // 2
        if len(values) % 2 == 1:
            return values[midpoint]
        return (values[midpoint - 1] + values[midpoint]) / Decimal("2")

    @property
    def worst_selected_test_return(self) -> Decimal:
        if not self.folds:
            raise ValueError("walk-forward result has no folds")
        return min(fold.selected_test_return for fold in self.folds)

    @property
    def best_selected_test_return(self) -> Decimal:
        if not self.folds:
            raise ValueError("walk-forward result has no folds")
        return max(fold.selected_test_return for fold in self.folds)

    @property
    def worst_selected_test_drawdown(self) -> Decimal:
        if not self.folds:
            raise ValueError("walk-forward result has no folds")
        return max(fold.selected_test_drawdown for fold in self.folds)

    @property
    def worst_selected_test_tail_loss(self) -> Decimal:
        if not self.folds:
            raise ValueError("walk-forward result has no folds")
        return max(fold.selected_test_tail_loss for fold in self.folds)

    def summary(self) -> dict[str, object]:
        return {
            "folds": len(self.folds),
            "selected_positive_folds": self.selected_positive_folds,
            "average_selected_test_return": decimal_to_str(self.average_selected_test_return),
            "median_selected_test_return": decimal_to_str(self.median_selected_test_return),
            "worst_selected_test_return": decimal_to_str(self.worst_selected_test_return),
            "best_selected_test_return": decimal_to_str(self.best_selected_test_return),
            "worst_selected_test_drawdown": decimal_to_str(self.worst_selected_test_drawdown),
            "worst_selected_test_tail_loss": decimal_to_str(self.worst_selected_test_tail_loss),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "created_at": self.created_at.isoformat(),
            "code_version": self.code_version,
            "grid": self.grid.to_dict(),
            "selection_policy": self.selection_policy.to_dict(),
            "summary": self.summary(),
            "folds": [fold.to_dict() for fold in self.folds],
        }


class WalkForwardRunner:
    def __init__(self, engine: BacktestEngine, *, code_version: str = "unknown") -> None:
        self._engine = engine
        self._code_version = code_version

    def run(
        self,
        *,
        base_config: BacktestConfig,
        grid: ParameterGrid,
        folds: tuple[WalkForwardFold, ...],
        experiment_id: str,
        selection_policy: SelectionPolicy | None = None,
    ) -> WalkForwardResult:
        policy = selection_policy or SelectionPolicy()
        fold_results = tuple(
            self._run_fold(base_config=base_config, grid=grid, fold=fold, selection_policy=policy)
            for fold in folds
        )
        return WalkForwardResult(
            experiment_id=experiment_id,
            strategy_id=base_config.strategy_id,
            created_at=datetime.now(tz=UTC),
            code_version=self._code_version,
            grid=grid,
            selection_policy=policy,
            folds=fold_results,
        )

    def _run_fold(
        self,
        *,
        base_config: BacktestConfig,
        grid: ParameterGrid,
        fold: WalkForwardFold,
        selection_policy: SelectionPolicy,
    ) -> WalkForwardFoldResult:
        raw_runs: list[tuple[ParameterCombination, dict[str, Decimal | int], dict[str, Decimal | int]]] = []
        for combination in grid.combinations():
            train_config = combination.apply(
                _config_for_window(
                    base_config,
                    start=fold.split.train_start,
                    end=fold.split.train_end,
                )
            )
            test_config = combination.apply(
                _config_for_window(
                    base_config,
                    start=fold.split.test_start,
                    end=fold.split.test_end,
                )
            )
            train_result = self._engine.run(train_config)
            test_result = self._engine.run(test_config)
            raw_runs.append((combination, train_result.metrics, test_result.metrics))

        ranked = sorted(raw_runs, key=lambda item: selection_policy.ranking_key(item[1]))
        runs = tuple(
            TrainTestRunSummary(
                rank=index + 1,
                run_id=combination.run_id,
                parameters=combination,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
            )
            for index, (combination, train_metrics, test_metrics) in enumerate(ranked)
        )
        best_test_run = sorted(
            runs,
            key=lambda run: (
                -_decimal_metric(run.test_metrics, "total_return"),
                _decimal_metric(run.test_metrics, "max_drawdown"),
                _decimal_metric(run.test_metrics, "turnover"),
            ),
        )[0]
        return WalkForwardFoldResult(
            fold=fold,
            selected_run=runs[0],
            best_test_run=best_test_run,
            runs=runs,
        )


def build_walk_forward_folds(
    *,
    start: datetime,
    end: datetime,
    train_months: int,
    test_months: int,
    step_months: int,
) -> tuple[WalkForwardFold, ...]:
    if train_months <= 0 or test_months <= 0 or step_months <= 0:
        raise ValueError("train_months, test_months, and step_months must be positive")
    folds: list[WalkForwardFold] = []
    fold_start = start
    fold_id = 1
    while True:
        train_start = fold_start
        train_end = add_months(train_start, train_months)
        test_start = train_end
        test_end = add_months(test_start, test_months)
        if test_end > end:
            break
        folds.append(
            WalkForwardFold(
                fold_id=fold_id,
                split=TrainTestSplit(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                ),
            )
        )
        fold_id += 1
        fold_start = add_months(fold_start, step_months)
    return tuple(folds)


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return value.replace(year=year, month=month)


def write_walk_forward_json(result: WalkForwardResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_walk_forward_csv(result: WalkForwardResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "fold_id",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "selected_run_id",
        "selected_fast_window",
        "selected_slow_window",
        "selected_fee_rate",
        "selected_slippage_bps",
        "selected_min_trend_strength",
        "selected_max_volatility",
        "selected_lookback_window",
        "selected_top_n",
        "selected_min_momentum",
        "selected_train_total_return",
        "selected_train_max_drawdown",
        "selected_train_tail_loss",
        "selected_train_turnover",
        "selected_test_total_return",
        "selected_test_max_drawdown",
        "selected_test_tail_loss",
        "selected_test_turnover",
        "selected_test_trade_count",
        "selected_test_average_risk_scale",
        "selected_test_risk_off_bars",
        "selected_test_recovery_bars",
        "selected_test_drawdown_stop_count",
        "selected_test_min_order_skipped_count",
        "selected_test_participation_capped_count",
        "selected_test_max_observed_participation_rate",
        "selected_test_estimated_participation_capacity_equity",
        "selected_test_positive",
        "best_test_run_id",
        "best_test_total_return",
    )
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for fold_result in result.folds:
            selected = fold_result.selected_run
            best_test = fold_result.best_test_run
            writer.writerow(
                {
                    "fold_id": fold_result.fold.fold_id,
                    **fold_result.fold.split.to_dict(),
                    "selected_run_id": selected.run_id,
                    "selected_fast_window": selected.parameters.fast_window,
                    "selected_slow_window": selected.parameters.slow_window,
                    "selected_fee_rate": decimal_to_str(selected.parameters.fee_rate),
                    "selected_slippage_bps": decimal_to_str(selected.parameters.slippage_bps),
                    "selected_min_trend_strength": decimal_to_str(
                        selected.parameters.min_trend_strength
                    ),
                    "selected_max_volatility": decimal_to_str(selected.parameters.max_volatility)
                    if selected.parameters.max_volatility is not None
                    else None,
                    "selected_lookback_window": selected.parameters.lookback_window,
                    "selected_top_n": selected.parameters.top_n,
                    "selected_min_momentum": decimal_to_str(selected.parameters.min_momentum),
                    "selected_train_total_return": decimal_to_str(
                        _decimal_metric(selected.train_metrics, "total_return")
                    ),
                    "selected_train_max_drawdown": decimal_to_str(
                        _decimal_metric(selected.train_metrics, "max_drawdown")
                    ),
                    "selected_train_tail_loss": decimal_to_str(
                        _decimal_metric(selected.train_metrics, "tail_loss")
                    ),
                    "selected_train_turnover": decimal_to_str(
                        _decimal_metric(selected.train_metrics, "turnover")
                    ),
                    "selected_test_total_return": decimal_to_str(
                        _decimal_metric(selected.test_metrics, "total_return")
                    ),
                    "selected_test_max_drawdown": decimal_to_str(
                        _decimal_metric(selected.test_metrics, "max_drawdown")
                    ),
                    "selected_test_tail_loss": decimal_to_str(
                        _decimal_metric(selected.test_metrics, "tail_loss")
                    ),
                    "selected_test_turnover": decimal_to_str(
                        _decimal_metric(selected.test_metrics, "turnover")
                    ),
                    "selected_test_trade_count": selected.test_metrics["trade_count"],
                    "selected_test_average_risk_scale": decimal_to_str(
                        _decimal_metric(selected.test_metrics, "average_risk_scale")
                    ),
                    "selected_test_risk_off_bars": selected.test_metrics["risk_off_bars"],
                    "selected_test_recovery_bars": selected.test_metrics["recovery_bars"],
                    "selected_test_drawdown_stop_count": selected.test_metrics["drawdown_stop_count"],
                    "selected_test_min_order_skipped_count": selected.test_metrics[
                        "min_order_skipped_count"
                    ],
                    "selected_test_participation_capped_count": selected.test_metrics[
                        "participation_capped_count"
                    ],
                    "selected_test_max_observed_participation_rate": decimal_to_str(
                        _decimal_metric(selected.test_metrics, "max_observed_participation_rate")
                    ),
                    "selected_test_estimated_participation_capacity_equity": decimal_to_str(
                        _decimal_metric(
                            selected.test_metrics,
                            "estimated_participation_capacity_equity",
                        )
                    ),
                    "selected_test_positive": selected.test_positive,
                    "best_test_run_id": best_test.run_id,
                    "best_test_total_return": decimal_to_str(
                        _decimal_metric(best_test.test_metrics, "total_return")
                    ),
                }
            )
    return output_path


def _config_for_window(config: BacktestConfig, *, start: datetime, end: datetime) -> BacktestConfig:
    from dataclasses import replace

    return replace(config, start=start, end=end)
