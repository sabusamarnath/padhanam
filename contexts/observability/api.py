"""Public read-only query interface for the observability context (D17).

The recommendation engine and any other context that needs trace
history calls through here. The real adapter lands when the
recommendation engine work begins; S7 ships the no-op stub so the
import-linter contracts and the cross-context wiring shape are real
today.
"""

from __future__ import annotations

from contexts.observability.domain.trace import TraceRecord, TraceSpan
from contexts.observability.ports import TraceQueryPort

__all__ = ["TraceQueryPort", "TraceRecord", "TraceSpan"]
