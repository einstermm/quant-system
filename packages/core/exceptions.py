"""Domain exceptions."""


class QuantSystemError(Exception):
    """Base class for all project-specific exceptions."""


class ConfigurationError(QuantSystemError):
    """Raised when runtime configuration is invalid or incomplete."""


class RiskRejectedError(QuantSystemError):
    """Raised when a trading action is blocked by risk controls."""


class ExecutionError(QuantSystemError):
    """Raised when an execution adapter cannot submit or reconcile an order."""


class HummingbotAdapterError(ExecutionError):
    """Raised when the Hummingbot integration fails or is not configured."""
