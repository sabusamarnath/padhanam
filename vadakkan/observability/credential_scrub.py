"""Credential-scrubbing logging filter (D34 control (a)).

Defense-in-depth around the structural rule that no code path passes
plaintext credential field values into log calls. The structural rule
is the primary control; this filter catches accidents.

Two detection layers:

1. ``extra`` dict references: any record whose ``extra`` keys (or the
   record attributes synthesised from them) name a plaintext credential
   field is dropped. Field names are checked against
   ``_FORBIDDEN_FIELD_NAMES`` and the value-object names that wrap
   plaintext (``TenantConnectionConfig``, ``connection_config``).

2. Message-string patterns: a record whose formatted message contains a
   ``key=value`` substring where the key matches a plaintext credential
   field name is dropped, regardless of whether the value is a real
   plaintext or a placeholder. The bias is to drop on suspicion rather
   than retain on benefit-of-the-doubt.

The filter is a leaf of the vadakkan import graph (no security imports,
no policy imports) so it can be installed at process boot before any
credential-bearing code paths execute. ``install_credential_scrub``
registers it on the root logger so every handler that processes
records inherits it.
"""

from __future__ import annotations

import logging
import re

# Field names whose presence in extra/attribute or in a key=value
# substring of a message indicates plaintext credential leakage.
_FORBIDDEN_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "host",
        "port",
        "database",
        "user",
        "username",
        "password",
        "dsn",
        # Value-object names that carry plaintext.
        "TenantConnectionConfig",
        "connection_config",
    }
)

# A key=value or key: value substring indicates structured logging that
# bypassed the extra dict and went directly into the message string.
_KEY_VALUE_PATTERN = re.compile(
    r"\b(?P<key>"
    + "|".join(re.escape(n) for n in _FORBIDDEN_FIELD_NAMES)
    + r")\s*[=:]\s*\S",
    re.IGNORECASE,
)


class CredentialScrubFilter(logging.Filter):
    """Drop log records that reference plaintext credential fields."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Layer 1: extra-dict-derived attributes. logging.Logger sets
        # the keys of `extra` directly on the record as attributes;
        # check the record's __dict__ for any forbidden name.
        for forbidden in _FORBIDDEN_FIELD_NAMES:
            if forbidden in record.__dict__:
                return False

        # Layer 2: key=value or key: value substrings in the formatted
        # message. getMessage() applies args formatting; we check the
        # post-format string so log("user=%s", plaintext) is also caught.
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        if _KEY_VALUE_PATTERN.search(message):
            return False

        return True


def install_credential_scrub() -> CredentialScrubFilter:
    """Install the filter on the root logger.

    Idempotent: subsequent calls return the existing filter rather than
    stacking duplicates. Returns the filter instance so callers can
    inspect or remove it (the latter only meaningful in tests).
    """
    root = logging.getLogger()
    for existing in root.filters:
        if isinstance(existing, CredentialScrubFilter):
            return existing
    f = CredentialScrubFilter()
    root.addFilter(f)
    # Also attach to existing handlers so records that bypass the
    # logger-level filter chain (rare, but possible with custom
    # configurations) are still scrubbed.
    for handler in root.handlers:
        already = any(
            isinstance(h, CredentialScrubFilter) for h in handler.filters
        )
        if not already:
            handler.addFilter(f)
    return f
