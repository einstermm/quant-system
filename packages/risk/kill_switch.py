"""Manual and automated kill switch state."""


class KillSwitch:
    def __init__(self, *, active: bool = False, reason: str = "") -> None:
        self._active = active
        self._reason = reason

    @property
    def active(self) -> bool:
        return self._active

    @property
    def reason(self) -> str:
        return self._reason

    def activate(self, reason: str) -> None:
        self._active = True
        self._reason = reason

    def release(self) -> None:
        self._active = False
        self._reason = ""
