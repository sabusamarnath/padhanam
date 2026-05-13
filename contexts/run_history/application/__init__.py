"""Run-history application layer (D17, D95).

Use cases for the run-history context. The producer-side
``record_run`` write-path use case lands at S31 commit 3; the
read-side query use cases shaped to Phase 2 UX consumption land
at S33 per the p9-epic forecast.
"""

from contexts.run_history.application.use_cases import record_run

__all__ = ["record_run"]
