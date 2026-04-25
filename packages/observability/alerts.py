"""Alerting interface placeholders."""


class AlertPublisher:
    def publish(self, *, title: str, message: str) -> None:
        raise NotImplementedError("configure Telegram, Discord, email, or SMS publisher")
