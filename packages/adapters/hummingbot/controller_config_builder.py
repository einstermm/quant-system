"""Build Hummingbot Strategy V2 controller configuration payloads."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ControllerConfigSpec:
    controller_name: str
    connector_name: str
    trading_pair: str
    total_amount_quote: Decimal
    extra: dict[str, object] = field(default_factory=dict)


class ControllerConfigBuilder:
    def build(self, spec: ControllerConfigSpec) -> dict[str, object]:
        payload: dict[str, object] = {
            "controller_name": spec.controller_name,
            "connector_name": spec.connector_name,
            "trading_pair": spec.trading_pair,
            "total_amount_quote": str(spec.total_amount_quote),
        }
        payload.update(spec.extra)
        return payload
