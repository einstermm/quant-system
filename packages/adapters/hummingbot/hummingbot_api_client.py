"""Thin Hummingbot API client boundary.

The first implementation is intentionally inert. Live API calls should only be
enabled after paper trading, sandbox credentials, and risk controls are tested.
"""

from dataclasses import dataclass

from packages.core.exceptions import HummingbotAdapterError


@dataclass(frozen=True, slots=True)
class HummingbotAPIConfig:
    base_url: str
    api_key: str | None = None
    timeout_seconds: int = 10


class HummingbotAPIClient:
    def __init__(self, config: HummingbotAPIConfig, *, live_enabled: bool = False) -> None:
        self._config = config
        self._live_enabled = live_enabled

    @property
    def live_enabled(self) -> bool:
        return self._live_enabled

    def submit_controller_config(self, controller_config: dict[str, object]) -> str:
        if not self._live_enabled:
            raise HummingbotAdapterError("Hummingbot live submission is disabled")
        raise NotImplementedError("wire Hummingbot API call after sandbox validation")
