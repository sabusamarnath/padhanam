"""EligibleLeversReader consumer port (D192, D194, S97b).

The composer asks for the tenant's **daily-cadence homeostatic** levers — the
levers the daily check-in prompts for. The eligibility predicate spans two
stores and so lives behind this port, satisfied by an ``apps/`` adapter
(Step-0 finding: goal ``mode`` is a Neo4j ``:Outcome`` property, not a Postgres
column, so eligible = ``:Outcome{mode:'homeostatic'}`` → its levers →
``expected_interval_days <= 1``; a progressive interval-1 goal like German is
correctly excluded by the mode-join). The check-in context never imports
daily_driver domain — it sees only ``EligibleLever``.

Framework-free; stdlib-only Protocol shape.
"""

from __future__ import annotations

from typing import Protocol

from shared_kernel import ActorContext

from contexts.checkin.domain.lever import EligibleLever


class EligibleLeversReader(Protocol):
    """Read-side consumer port for the daily check-in's eligible levers."""

    async def list_eligible(
        self, *, actor: ActorContext
    ) -> tuple[EligibleLever, ...]:
        """Daily-cadence homeostatic levers for the actor's tenant.

        Empty when the tenant has no eligible levers (the composer then
        sends nothing — there is nothing to check in on).
        """
        ...


__all__ = ["EligibleLeversReader"]
