"""Calendar domain errors (D148).

``SyncTokenExpiredError`` is domain-meaningful: it is the signal the
pull pipeline reacts to by clearing the stored sync token and performing
a full resync (the Google ``410 GONE`` path, reconciled against the
current API docs). The transport errors mirror ingestion's
retryable/non-retryable split (EmbedderError vs EmbedderConfigurationError)
so the pipeline can distinguish a transient failure worth retrying from a
configuration/auth failure that will not self-resolve.

Framework-free per D16 — these are plain exceptions, no vendor types.
"""

from __future__ import annotations


class CalendarSourceError(Exception):
    """Transient failure fetching events (5xx, network). Retryable."""


class CalendarSourceConfigurationError(Exception):
    """Non-retryable failure: auth/scope/config (401, 403, 400)."""


class SyncTokenExpiredError(Exception):
    """The stored sync token expired (HTTP 410 GONE).

    The pipeline must clear its stored sync token and perform a full
    resync without a sync token.
    """


class NoSuchConnectionError(Exception):
    """The requested calendar connection does not exist for the tenant."""
