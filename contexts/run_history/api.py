"""Public query interface for the run-history context (D17, D94, D95).

Per D17, every context exposes a single ``api.py`` at its root
with the read-only query methods other contexts may call.

The run-history context's producer surface lands across the P9
session arc:

- ``record_run`` (S31 commit 3): the runs-row write seam consumed
  by the agent context via the ``RunHistoryWriter`` consumer
  port at
  ``contexts/agent/application/ports/run_history_writer.py``.
- UX-shaped query port (S33): the Phase 2 UX read surface for
  individual run rendering, run listing with filters, citation
  surface fetch.
- HTTP API (S34): the ingestion management surface absorbed
  from the P6 carryover per the p9-epic forecast.

At S31 commit 3 the surface is the ``record_run`` use case
re-exported via the api-facade-via-callable pattern from D17.
"""

from __future__ import annotations

from contexts.run_history.application import record_run

__all__ = ["record_run"]
