"""Execution client backed by Hummingbot."""

from packages.adapters.hummingbot.hummingbot_api_client import HummingbotAPIClient
from packages.adapters.hummingbot.order_mapper import OrderMapper
from packages.execution.order_intent import OrderIntent


class HummingbotExecutorClient:
    def __init__(self, api_client: HummingbotAPIClient, order_mapper: OrderMapper | None = None) -> None:
        self._api_client = api_client
        self._order_mapper = order_mapper or OrderMapper()

    def submit_order_intent(self, intent: OrderIntent) -> str:
        payload = self._order_mapper.to_hummingbot_payload(intent)
        return self._api_client.submit_controller_config(payload)
