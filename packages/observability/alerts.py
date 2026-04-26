"""Alerting primitives for local monitoring and paper readiness checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Alert:
    severity: str
    title: str
    message: str
    created_at: datetime

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }


def info_alert(title: str, message: str) -> Alert:
    return _alert("INFO", title, message)


def warning_alert(title: str, message: str) -> Alert:
    return _alert("WARN", title, message)


def critical_alert(title: str, message: str) -> Alert:
    return _alert("CRITICAL", title, message)


def _alert(severity: str, title: str, message: str) -> Alert:
    return Alert(
        severity=severity,
        title=title,
        message=message,
        created_at=datetime.now(tz=UTC),
    )


class AlertPublisher:
    def publish(self, *, title: str, message: str) -> None:
        raise NotImplementedError("configure Telegram, Discord, email, or SMS publisher")
