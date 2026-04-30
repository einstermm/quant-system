"""Deployment status helpers for the web API."""

from __future__ import annotations

from pathlib import Path

from apps.web_api.auth import auth_status
from apps.web_api.status import REPO_ROOT

FRONTEND_DIST_PATH = Path("apps/web_frontend/dist")
DOCKERFILE_PATH = Path("Dockerfile")
COMPOSE_PATH = Path("docker-compose.yml")


def build_deployment_status(*, repo_root: Path = REPO_ROOT) -> dict[str, object]:
    frontend_dist = repo_root / FRONTEND_DIST_PATH
    compose_path = repo_root / COMPOSE_PATH
    compose_text = compose_path.read_text(encoding="utf-8") if compose_path.exists() else ""

    return {
        "mode": "single_container_web",
        "api_root": "/",
        "static_frontend_url": "/app",
        "frontend_dist_path": str(FRONTEND_DIST_PATH),
        "frontend_static_ready": (frontend_dist / "index.html").exists(),
        "dockerfile_path": str(DOCKERFILE_PATH),
        "dockerfile_ready": (repo_root / DOCKERFILE_PATH).exists(),
        "compose_path": str(COMPOSE_PATH),
        "compose_web_service_ready": "\n  web:" in compose_text or compose_text.startswith("web:"),
        "state_mounts_required": ["data", "reports", "logs"],
        "auth": auth_status(),
    }
