"""Train/test parameter robustness validation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, replace
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


@dataclass(frozen=True, slots=True)
class TrainTestSplit:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime

    def __post_init__(self) -> None:
        if self.train_start.tzinfo is None or self.train_end.tzinfo is None:
            raise ValueError("train timestamps must be timezone-aware")
        if self.test_start.tzinfo is None or self.test_end.tzinfo is None:
            raise ValueError("test timestamps must be timezone-aware")
        if self.train_start >= self.train_end:
            raise ValueError("train_start must be before train_end")
        if self.test_start >= self.test_end:
            raise ValueError("test_start must be before test_end")
        if self.train_end > self.test_start:
            raise ValueError("train_end cannot be after test_start")

    def to_dict(self) -> dict[str, str]:
        return {
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TrainTestRunSummary:
    rank: int
    run_id: str
    parameters: ParameterCombination
    train_metrics: dict[str, Decimal | int]
    test_metrics: dict[str, Decimal | int]

    @property
    def return_gap(self) -> Decimal:
        return _decimal_metric(self.train_metrics, "total_return") - _decimal_metric(
            self.test_metrics,
            "total_return",
        )

    @property
    def test_positive(self) -> bool:
        return _decimal_metric(self.test_metrics, "total_return") > Decimal("0")

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "run_id": self.run_id,
            "parameters": self.parameters.to_dict(),
            "return_gap": decimal_to_str(self.return_gap),
            "test_positive": self.test_positive,
            "train_metrics": _metrics_to_dict(self.train_metrics),
            "test_metrics": _metrics_to_dict(self.test_metrics),
        }


@dataclass(frozen=True, slots=True)
class TrainTestValidationResult:
    experiment_id: str
    strategy_id: str
    created_at: datetime
    code_version: str
    split: TrainTestSplit
    grid: ParameterGrid
    selection_policy: SelectionPolicy
    runs: tuple[TrainTestRunSummary, ...]

    @property
    def best_train_run(self) -> TrainTestRunSummary:
        if not self.runs:
            raise ValueError("validation result has no runs")
        return self.runs[0]

    @property
    def best_test_run(self) -> TrainTestRunSummary:
        if not self.runs:
            raise ValueError("validation result has no runs")
        return sorted(
            self.runs,
            key=lambda run: (
                -_decimal_metric(run.test_metrics, "total_return"),
                _decimal_metric(run.test_metrics, "max_drawdown"),
                _decimal_metric(run.test_metrics, "turnover"),
            ),
        )[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "created_at": self.created_at.isoformat(),
            "code_version": self.code_version,
            "split": self.split.to_dict(),
            "grid": self.grid.to_dict(),
            "selection_policy": self.selection_policy.to_dict(),
            "best_train_run": self.best_train_run.to_dict(),
            "best_test_run": self.best_test_run.to_dict(),
            "runs": [run.to_dict() for run in self.runs],
        }


class TrainTestValidationRunner:
    def __init__(self, engine: BacktestEngine, *, code_version: str = "unknown") -> None:
        self._engine = engine
        self._code_version = code_version

    def run(
        self,
        *,
        base_config: BacktestConfig,
        grid: ParameterGrid,
        split: TrainTestSplit,
        experiment_id: str,
        selection_policy: SelectionPolicy | None = None,
    ) -> TrainTestValidationResult:
        policy = selection_policy or SelectionPolicy()
        raw_runs: list[tuple[ParameterCombination, dict[str, Decimal | int], dict[str, Decimal | int]]] = []
        for combination in grid.combinations():
            train_config = _config_for_window(
                combination.apply(base_config),
                start=split.train_start,
                end=split.train_end,
            )
            test_config = _config_for_window(
                combination.apply(base_config),
                start=split.test_start,
                end=split.test_end,
            )
            train_result = self._engine.run(train_config)
            test_result = self._engine.run(test_config)
            raw_runs.append((combination, train_result.metrics, test_result.metrics))

        ranked = sorted(raw_runs, key=lambda item: policy.ranking_key(item[1]))
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
        return TrainTestValidationResult(
            experiment_id=experiment_id,
            strategy_id=base_config.strategy_id,
            created_at=datetime.now(tz=UTC),
            code_version=self._code_version,
            split=split,
            grid=grid,
            selection_policy=policy,
            runs=runs,
        )


def write_train_test_validation_json(result: TrainTestValidationResult, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def write_train_test_validation_csv(result: TrainTestValidationResult, path: str | Path) -> Path:
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
        "train_total_return",
        "train_max_drawdown",
        "train_tail_loss",
        "train_turnover",
        "train_trade_count",
        "test_total_return",
        "test_max_drawdown",
        "test_tail_loss",
        "test_turnover",
        "test_trade_count",
        "return_gap",
        "test_positive",
    )

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for run in result.runs:
            writer.writerow(
                {
                    "rank": run.rank,
                    "run_id": run.run_id,
                    **run.parameters.to_dict(),
                    "train_total_return": decimal_to_str(
                        _decimal_metric(run.train_metrics, "total_return")
                    ),
                    "train_max_drawdown": decimal_to_str(
                        _decimal_metric(run.train_metrics, "max_drawdown")
                    ),
                    "train_tail_loss": decimal_to_str(
                        _decimal_metric(run.train_metrics, "tail_loss")
                    ),
                    "train_turnover": decimal_to_str(
                        _decimal_metric(run.train_metrics, "turnover")
                    ),
                    "train_trade_count": run.train_metrics["trade_count"],
                    "test_total_return": decimal_to_str(
                        _decimal_metric(run.test_metrics, "total_return")
                    ),
                    "test_max_drawdown": decimal_to_str(
                        _decimal_metric(run.test_metrics, "max_drawdown")
                    ),
                    "test_tail_loss": decimal_to_str(
                        _decimal_metric(run.test_metrics, "tail_loss")
                    ),
                    "test_turnover": decimal_to_str(
                        _decimal_metric(run.test_metrics, "turnover")
                    ),
                    "test_trade_count": run.test_metrics["trade_count"],
                    "return_gap": decimal_to_str(run.return_gap),
                    "test_positive": run.test_positive,
                }
            )

    return output_path


def _config_for_window(config: BacktestConfig, *, start: datetime, end: datetime) -> BacktestConfig:
    return replace(config, start=start, end=end)


def _metrics_to_dict(metrics: dict[str, Decimal | int]) -> dict[str, object]:
    return {
        key: decimal_to_str(value) if isinstance(value, Decimal) else value
        for key, value in metrics.items()
    }
