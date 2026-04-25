"""Health check primitives."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    name: str
    healthy: bool
    detail: str = ""
