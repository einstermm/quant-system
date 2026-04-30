"""Build external alert outbox payloads without sending secrets from Web."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExternalAlertOutboxResult:
    status: str
    generated_at: datetime
    channel: str
    severity: str
    title: str
    message: str
    dispatch_enabled: bool
    payload: dict[str, object]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "channel": self.channel,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "dispatch_enabled": self.dispatch_enabled,
            "payload": self.payload,
            "artifacts": self.artifacts,
        }


def build_external_alert_outbox(
    *,
    output_dir: str | Path,
    channel: str,
    severity: str,
    title: str,
    message: str,
    dispatch_enabled: bool = False,
) -> ExternalAlertOutboxResult:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(tz=UTC)
    payload = {
        "channel": channel,
        "severity": severity.upper(),
        "title": title,
        "message": message,
        "generated_at": generated_at.isoformat(),
        "source": "quant-system-web",
    }
    status = "external_alert_dispatch_not_configured"
    if dispatch_enabled:
        status = "external_alert_dispatch_blocked_requires_worker"
    artifacts = {
        "alert_payload_json": str(output_path / "alert_payload.json"),
        "alert_outbox_jsonl": str(output_path / "alert_outbox.jsonl"),
    }
    result = ExternalAlertOutboxResult(
        status=status,
        generated_at=generated_at,
        channel=channel,
        severity=severity.upper(),
        title=title,
        message=message,
        dispatch_enabled=dispatch_enabled,
        payload=payload,
        artifacts=artifacts,
    )
    (output_path / "alert_payload.json").write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    with (output_path / "alert_outbox.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")
    return result
