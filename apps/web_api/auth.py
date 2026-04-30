"""Lightweight API-key write guard for the web API."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException


API_KEY_ENV = "QUANT_WEB_API_KEY"


def auth_status() -> dict[str, object]:
    return {
        "auth_enabled": bool(os.environ.get(API_KEY_ENV, "")),
        "mode": "api_key" if os.environ.get(API_KEY_ENV, "") else "disabled_dev",
        "write_header": "X-Quant-Api-Key",
    }


def require_write_auth(x_quant_api_key: str = Header(default="")) -> None:
    expected = os.environ.get(API_KEY_ENV, "")
    if not expected:
        return
    if x_quant_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
