"""Safe read-only artifact access for the web console."""

from __future__ import annotations

import json
from pathlib import Path

from apps.web_api.status import REPO_ROOT


ALLOWED_PREFIXES = (
    "docs/",
    "reports/",
    "strategies/",
    "data/reports/",
    "data/samples/",
)
MAX_ARTIFACT_BYTES = 1_000_000
MAX_TEXT_CHARS = 120_000
MAX_JSONL_LINES = 500
MAX_CSV_LINES = 500


def read_artifact(path: str, repo_root: Path = REPO_ROOT) -> dict[str, object]:
    safe_path = _safe_relative_path(path)
    absolute = (repo_root / safe_path).resolve()
    repo = repo_root.resolve()
    if not _is_inside(absolute, repo):
        raise ValueError("artifact path must stay inside the repository")
    normalized = safe_path.as_posix()
    if not any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise ValueError("artifact path is outside the web-readable allowlist")
    if not absolute.exists():
        return {
            "path": normalized,
            "exists": False,
            "kind": _kind(safe_path),
            "size_bytes": 0,
            "truncated": False,
            "content": "",
            "error": "artifact does not exist",
        }
    if not absolute.is_file():
        raise ValueError("artifact path must point to a file")

    size = absolute.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        return {
            "path": normalized,
            "exists": True,
            "kind": _kind(safe_path),
            "size_bytes": size,
            "truncated": True,
            "content": "",
            "error": f"artifact is larger than {MAX_ARTIFACT_BYTES} bytes",
        }

    kind = _kind(safe_path)
    content = _read_content(absolute, kind)
    truncated = False
    if len(content) > MAX_TEXT_CHARS:
        content = content[:MAX_TEXT_CHARS] + "\n...[truncated]"
        truncated = True

    return {
        "path": normalized,
        "exists": True,
        "kind": kind,
        "size_bytes": size,
        "truncated": truncated,
        "content": content,
        "error": "",
    }


def _safe_relative_path(path: str) -> Path:
    if not path or not path.strip():
        raise ValueError("artifact path is required")
    candidate = Path(path)
    if candidate.is_absolute():
        raise ValueError("artifact path must be relative")
    if any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("artifact path cannot contain empty/current/parent segments")
    return candidate


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".jsonl":
        return "jsonl"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".csv":
        return "csv"
    if suffix in {".yml", ".yaml"}:
        return "yaml"
    if suffix == ".txt":
        return "text"
    return "text"


def _read_content(path: Path, kind: str) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if kind == "json":
        try:
            return json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False)
        except json.JSONDecodeError:
            return text
    if kind == "jsonl":
        return "\n".join(text.splitlines()[:MAX_JSONL_LINES])
    if kind == "csv":
        return "\n".join(text.splitlines()[:MAX_CSV_LINES])
    return text
