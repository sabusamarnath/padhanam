"""Public query interface for the run-history context (D17, D94, D95).

Per D17, every context exposes a single ``api.py`` at its root with
the read-only query methods other contexts may call.

The run-history context's producer surface lands across the P9
session arc: the ``record_run`` use case at S31 commit 3 (the
runs-row write seam consumed by the agent context via the
``RunHistoryWriter`` consumer port at
``contexts/agent/application/ports/run_history_writer.py``); the
UX-shaped query port at S33 (the Phase 2 UX read surface); the
HTTP API at S34 (the ingestion management surface absorbed from
the P6 carryover).

At S31 commit 2 the surface is empty: the skeleton lands the
bounded context and the ``RunRecord`` domain value object only.
``record_run`` lands at commit 3 alongside the
``RunHistoryRepositoryPort`` definition.
"""

from __future__ import annotations

__all__: list[str] = []
