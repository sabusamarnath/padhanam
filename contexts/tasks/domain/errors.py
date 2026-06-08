"""Task ingestion error taxonomy (D167).

Mirrors the calendar/email source errors: a retryable transport/5xx failure
(``TaskSourceError``) vs a non-retryable config/auth/4xx failure
(``TaskSourceConfigurationError``), plus the missing-connection error.
"""

from __future__ import annotations


class TaskSourceError(Exception):
    """Retryable task-source failure (network, timeout, 5xx)."""


class TaskSourceConfigurationError(Exception):
    """Non-retryable task-source failure (auth, scope, malformed request, 4xx)."""


class NoSuchConnectionError(Exception):
    """No task connection exists for the given id/tenant."""


__all__ = [
    "NoSuchConnectionError",
    "TaskSourceConfigurationError",
    "TaskSourceError",
]
