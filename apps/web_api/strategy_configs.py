"""Safe online editing for whitelisted strategy config files."""

from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path

from apps.web_api.jobs import STRATEGY_OPTIONS
from apps.web_api.state_db import record_state_document
from apps.web_api.status import REPO_ROOT

ALLOWED_STRATEGY_CONFIG_FILES = {"config.yml", "risk.yml", "backtest.yml", "portfolio.yml"}
STRATEGY_CONFIG_BACKUP_ROOT = Path("reports/web_reviews/strategy_config_backups")
MAX_CONFIG_BYTES = 50_000


def list_strategy_configs(*, repo_root: Path = REPO_ROOT) -> dict[str, object]:
    strategies: list[dict[str, object]] = []
    for strategy_id, relative_dir in STRATEGY_OPTIONS.items():
        strategy_dir = repo_root / relative_dir
        files = [_file_item(strategy_dir, file_name, relative_dir) for file_name in sorted(ALLOWED_STRATEGY_CONFIG_FILES)]
        strategies.append(
            {
                "strategy_id": strategy_id,
                "label": strategy_id,
                "path": relative_dir,
                "files": files,
            }
        )
    return {
        "allowed_files": sorted(ALLOWED_STRATEGY_CONFIG_FILES),
        "max_config_bytes": MAX_CONFIG_BYTES,
        "backup_root": str(STRATEGY_CONFIG_BACKUP_ROOT),
        "strategies": strategies,
    }


def read_strategy_config(
    *,
    strategy_id: str,
    file_name: str,
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    path, relative_path = _safe_config_path(strategy_id, file_name, repo_root)
    if not path.exists():
        raise ValueError("strategy config file does not exist")
    content = path.read_text(encoding="utf-8")
    return {
        "strategy_id": strategy_id,
        "file_name": file_name,
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(content),
        "updated_at": _mtime(path),
        "content": content,
    }


def update_strategy_config(
    *,
    strategy_id: str,
    file_name: str,
    content: str,
    operator_note: str = "",
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    path, relative_path = _safe_config_path(strategy_id, file_name, repo_root)
    _validate_content(strategy_id=strategy_id, file_name=file_name, content=content)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup_path(strategy_id=strategy_id, file_name=file_name, repo_root=repo_root)
    if path.exists():
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
    path.write_text(content, encoding="utf-8")

    payload = {
        "strategy_id": strategy_id,
        "file_name": file_name,
        "path": relative_path,
        "backup_path": _relative_to_repo(backup_path, repo_root),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(content),
        "updated_at": datetime.now(tz=UTC).isoformat(),
        "operator_note": operator_note.strip()[:1000],
    }
    record_state_document(
        key=f"strategy_config:{strategy_id}:{file_name}",
        source_path=relative_path,
        payload=payload,
        repo_root=repo_root,
    )
    return payload


def _file_item(strategy_dir: Path, file_name: str, relative_dir: str) -> dict[str, object]:
    path = strategy_dir / file_name
    return {
        "file_name": file_name,
        "path": f"{relative_dir}/{file_name}",
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "updated_at": _mtime(path) if path.exists() else "",
    }


def _safe_config_path(strategy_id: str, file_name: str, repo_root: Path) -> tuple[Path, str]:
    if strategy_id not in STRATEGY_OPTIONS:
        raise ValueError(f"unsupported strategy: {strategy_id}")
    if file_name not in ALLOWED_STRATEGY_CONFIG_FILES:
        raise ValueError(f"unsupported strategy config file: {file_name}")
    relative_dir = STRATEGY_OPTIONS[strategy_id]
    path = (repo_root / relative_dir / file_name).resolve()
    strategy_dir = (repo_root / relative_dir).resolve()
    if strategy_dir not in [path, *path.parents]:
        raise ValueError("strategy config path escapes strategy directory")
    return path, f"{relative_dir}/{file_name}"


def _validate_content(*, strategy_id: str, file_name: str, content: str) -> None:
    encoded = content.encode("utf-8")
    if not content.strip():
        raise ValueError("strategy config content cannot be empty")
    if len(encoded) > MAX_CONFIG_BYTES:
        raise ValueError(f"strategy config content exceeds {MAX_CONFIG_BYTES} bytes")
    if "\x00" in content:
        raise ValueError("strategy config content contains NUL byte")
    if file_name in {"config.yml", "backtest.yml"} and f"strategy_id: {strategy_id}" not in content:
        raise ValueError("config/backtest file must keep the matching strategy_id")


def _backup_path(*, strategy_id: str, file_name: str, repo_root: Path) -> Path:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_file = file_name.replace(".", "_")
    return repo_root / STRATEGY_CONFIG_BACKUP_ROOT / strategy_id / f"{timestamp}_{safe_file}.bak"


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def _relative_to_repo(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
