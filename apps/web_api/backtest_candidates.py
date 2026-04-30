"""Shared helpers for confirmed backtest candidate metadata."""

from __future__ import annotations

import json
from pathlib import Path

from apps.web_api.status import REPO_ROOT


BACKTEST_CANDIDATE_PATH = Path("reports/web_reviews/backtest_candidate.json")


def read_backtest_candidate(repo_root: Path = REPO_ROOT) -> dict[str, object] | None:
    path = repo_root / BACKTEST_CANDIDATE_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
