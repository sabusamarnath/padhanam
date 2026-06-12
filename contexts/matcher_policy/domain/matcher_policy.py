"""MatcherPolicy — the active matcher policy (D186/S91b).

A single ``suppress_single_signal`` flag now: when active, the matcher does not
emit single-signal ``goal-name`` keyword-on-name candidate edges (S91a's
gate-confirmed cross-goal noise). A tenant with no policy row reads
``inactive()`` — flag off, the matcher behaves exactly as the S90 baseline.

The rule-set/policy-content abstraction (a set of active rules, not one flag)
lands at the second rule (cross-domain), the second instance — built when a
second policy exists to generalise over, not before.

Pure domain (D16): stdlib only, no content (no titles/senders/subjects).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatcherPolicy:
    """The active matcher policy for one tenant."""

    suppress_single_signal: bool = False

    @classmethod
    def inactive(cls) -> "MatcherPolicy":
        """The default — no policy applied (flag off)."""
        return cls(suppress_single_signal=False)


__all__ = ["MatcherPolicy"]
