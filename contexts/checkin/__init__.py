"""The check-in bounded context — the daily three-state completion capture (D192, D194, S97b).

The check-in is the **pending-only (outbound-initiated)** ConversationFlow
cell (D194): the DAILY_SCHEDULED composer sends a compact goal-level prompt
and creates a PendingClarification (``target_cell='checkin'``); the operator's
free-text reply routes to this cell by the active-pending path (D140); the
cell parses the reply against the eligible levers, echoes a declarative
confirm, and on confirm writes the three-state outcome — a ``did`` to
``commitment_completions`` (the single did-source), a ``reported_didnt`` to
``commitment_checkin_responses``, and silence to neither.

Cross-context access is via this context's ``application.ports`` consumer
Protocols, satisfied by adapters wired in ``apps/`` (the legal D17 seam) —
the eligible-lever traversal (Neo4j mode-join + Postgres interval) and the
two-store write live behind ports, so this context never imports
``daily_driver`` domain across the boundary.
"""
