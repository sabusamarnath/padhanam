"""Source pipeline state (D60 / D61).

The per-stage status field that drives D60's worker reentrancy
seam. At S19 the state space covers only the parsing stage. S20
extends it with embedding-stage values; S21 extends with extraction-
stage values; the str-enum shape stays stable as new values land.

A source row's lifecycle at S19:

    received  -- the upload-side use case writes this on register;
                  workers claim rows in this state for parsing.
        |
        v
    parsing   -- the worker transitions to this on claim, before
                  invoking the parser. Surfaces "in-flight" to
                  observers and disambiguates from received-but-
                  not-yet-claimed.
        |
        +--> parsed  -- worker transitions on parser success after
        |              writing chunks atomically.
        |
        +--> failed  -- worker transitions on parser exception;
                        parsing_error_text on the row carries the
                        reason. Operator manually flips back to
                        received for retry at S19; richer retry
                        semantics defer to production-deployment
                        context.

Domain code is framework-free per D16 — stdlib StrEnum, no
Pydantic, no SQLAlchemy.
"""

from __future__ import annotations

from enum import StrEnum


class SourceState(StrEnum):
    RECEIVED = "received"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"
