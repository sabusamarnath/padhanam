"""Run-history application layer (D17, D95, D97).

- ``record_run`` use case at ``use_cases.py`` is the producer-side
  write seam (S31, D95) consumed by the agent context via the
  consumer-side ``RunHistoryWriter`` port.
- ``cursor`` module at ``cursor.py`` carries the ``encode`` /
  ``decode`` helpers for the read-side ``RunListCursor`` opaque
  string serialisation (S33, D97). The HTTP layer at S34/S35
  uses the helpers at the request/response boundary; the port
  itself accepts the structured cursor value object.

No read-side use case lands at S33: auth and request shaping
happen at the HTTP layer; the port surface accepts the dependency-
injected reader directly.
"""

from contexts.run_history.application.use_cases import record_run

__all__ = ["record_run"]
