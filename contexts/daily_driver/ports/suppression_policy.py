"""Suppression-policy port for the matcher (D186/S91b).

The read half of the apply seam, from the matcher's side. ``correlate_goal_facets``
reads the active policy at the pre-`replace_goal_edges` hook and suppresses
single-signal candidates when it is active — so an applied recommendation changes
the matcher on every run, surviving the derived-state recompute (D155).

The port is **daily_driver's own** — this context imports nothing from the policy
surface (`matcher_policy`) or from `optimization`. The apps bridge implements it
over `matcher_policy`'s reader port (D17). Default-None at the call site, so
correlation runs unchanged (flag off) when the seam is not wired.

Ports layer is pure per D16.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import ActorContext


class SuppressionPolicy(Protocol):
    """Reads whether matcher single-signal suppression is active for the actor."""

    async def suppress_single_signal(self, *, actor: ActorContext) -> bool:
        """True when the single-signal suppression flag is active (D186)."""
        ...


__all__ = ["SuppressionPolicy"]
