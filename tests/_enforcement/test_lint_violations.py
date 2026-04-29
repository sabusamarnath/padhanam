"""How to verify import-linter actually catches what it claims.

The contracts in ``.importlinter`` are only worth the bytes they cost if
they fail when given a violation. To verify, drop a probe file like the
example below into a contract's ``source_modules`` tree, run
``uv run lint-imports``, and confirm the contract reports BROKEN. Then
remove the probe.

Example probe — drop at ``contexts/audit/domain/_violation_probe.py``::

    import pydantic  # forbidden by Contract 1

Verified once at S5 close (2026-04-29): the probe broke ``Domain code is
pure`` as expected, and removing it returned the suite to ``3 kept,
0 broken``. Re-verify any time the contract definitions are edited or a
new contract is added.
"""

from __future__ import annotations
