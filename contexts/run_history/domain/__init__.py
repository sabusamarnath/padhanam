"""Run-history domain layer (D17, D95).

Domain value object at ``run_record.py``. The frozen ``RunRecord``
dataclass carries the fifteen-column shape D95 commits for the
``runs`` per-tenant table; invariants are enforced in
``__post_init__`` so the writer adapter cannot persist a row that
fails the domain rules.
"""

from contexts.run_history.domain.run_record import RunRecord

__all__ = ["RunRecord"]
