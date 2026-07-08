"""EmailJobSearchSource — the rule-confirmed job-search emails (D183/S89).

A consumer-defined read port (D17): the daily-driver moat reads which email
facets the rules confirmed as job-search activity, to write the classifier-fed
SERVES edge to Get a job and to fold the activity to a count. The verdict is
persisted on the email store (S89), so this reads durable state, not a one-run
artefact. The daily-driver context never imports the email store directly; an
``apps/`` adapter composes the email store behind this port.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared_kernel import ActorContext

# The source class a goal declares (``:Outcome.ingests_source_class``) to ingest the
# rule-confirmed job-search emails (S103ah, D240). The correlation engine binds this
# source's evidence to whichever goal carries the flag — so the engine names a *source
# class* (this ingestion path), never a specific job goal, retiring the one place a goal
# name was hardcoded inside the otherwise goal-agnostic engine (the retired
# ``_JOB_SEARCH_GOAL_NAME``). The per-goal flag is dogfood-set by an ops script.
EMAIL_JOB_SEARCH_SOURCE_CLASS = "email_job_search"


@dataclass(frozen=True)
class EmailJobSearchClassification:
    """One rule-confirmed job-search email. ``facet_id`` is the email's id —
    the ``:Facet`` ``facet_id`` the SERVES edge keys on; ``kind`` is the
    classifier verdict (application / interview / …); ``occurred_at`` is the
    received time driving the recency-active reading."""

    facet_id: UUID
    kind: str
    occurred_at: datetime | None


class EmailJobSearchSource(Protocol):
    async def list_confirmed(
        self, *, actor: ActorContext
    ) -> tuple[EmailJobSearchClassification, ...]:
        """The tenant's rule-confirmed job-search emails (job_search_kind set)."""
        ...


__all__ = [
    "EMAIL_JOB_SEARCH_SOURCE_CLASS",
    "EmailJobSearchClassification",
    "EmailJobSearchSource",
]
