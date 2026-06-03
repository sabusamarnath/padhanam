"""Email domain errors (D151).

Mirrors the calendar errors' retryable/non-retryable split. There is no
incremental-cursor-expiry error analogous to calendar's
``SyncTokenExpiredError`` because S56a builds full-pull-only — the Gmail
``history.list`` 404 path is dormant per D151 and lands with the
incremental graduation, not here.

Framework-free per D16 — plain exceptions, no vendor types.
"""

from __future__ import annotations


class EmailSourceError(Exception):
    """Transient failure fetching messages (5xx, network). Retryable."""


class EmailSourceConfigurationError(Exception):
    """Non-retryable failure: auth/scope/config (401, 403, 400)."""


class NoSuchConnectionError(Exception):
    """The requested email connection does not exist for the tenant."""
