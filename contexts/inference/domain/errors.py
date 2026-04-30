"""Domain errors raised across the InferencePort boundary.

LiteLLM exceptions never leak past the adapter (D16): the adapter maps
its vendor exceptions to one of these domain exceptions before
re-raising. Callers catch the domain shape, not vendor-specific types.
"""

from __future__ import annotations


class InferenceError(Exception):
    """Base for every inference domain error."""


class InferenceUnavailable(InferenceError):
    """The gateway is reachable but cannot service the request right now.

    Maps from rate-limit, capacity, and upstream-overload signals. Callers
    treat this as retryable.
    """


class InferenceConfigurationError(InferenceError):
    """The gateway rejected the request due to client configuration.

    Examples: unknown model name, missing/invalid auth at the gateway,
    malformed request shape. Callers do not retry these.
    """


class InferenceTimeout(InferenceError):
    """The gateway did not respond within the deadline."""
