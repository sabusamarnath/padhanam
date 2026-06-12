"""classify_job_search use case — label the stored emails (D183, S89).

Reads the live emails (decrypted sender + subject), runs the rules-only
classifier (domain), and **persists** each verdict on the email row
(``job_search_kind``) so ``correlate_goal_facets`` re-reads it on every
recompute and the Get-a-job SERVES edges stay durable. Idempotent — re-running
after tightening the rules overwrites the column, so the edges follow the rules.
Counts only; no senders/subjects leave the process.

The **calibrated evidence bar** (D184) lives here, not in the pure classifier: a
high-signal kind (offer / interview) minted from an *unknown* sender on a bare
subject keyword is the failure mode that put a newsletter "offer" and a
newsletter "interview" on the moat's top cells (S89). The bar scales with signal
weight — a high-signal verdict from an unknown sender survives only when its
thread already carries job-search signal (a known-sender or application-shaped
email shares its ``thread_id``). This use case sees every email, so it can read
that thread context the pure ``classify`` cannot.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from contexts.email.domain.email import Email
from contexts.email.domain.job_search_classifier import (
    HIGH_SIGNAL_KINDS,
    classify,
    is_known_sender,
)
from shared_kernel import TenantContext

# Kinds whose presence in a thread makes it a *job-context thread* — the
# application-shaped anchor that licenses a high-signal reply from an unknown
# sender (D184). An offer/interview does not anchor (it is the thing being
# gated); a lone newsletter therefore cannot vouch for itself.
_ANCHOR_KINDS = frozenset({"application", "acknowledgement"})


class _EmailClassifyStore(Protocol):
    async def list_emails(
        self, *, tenant_context: TenantContext, include_deleted: bool = ...
    ) -> tuple[Email, ...]: ...

    async def set_job_search_kinds(
        self, *, tenant_context: TenantContext, verdicts: dict[str, str | None]
    ) -> int: ...


@dataclass(frozen=True)
class ClassifyResult:
    total: int
    confirmed: int
    by_kind: dict[str, int] = field(default_factory=dict)
    updated: int = 0


async def classify_job_search_emails(
    *, tenant_context: TenantContext, emails: _EmailClassifyStore
) -> ClassifyResult:
    rows = await emails.list_emails(tenant_context=tenant_context)

    # Pass 1: the per-email rules verdict (sender + subject only).
    prelim: list[tuple[Email, bool, str | None, bool]] = []
    for e in rows:
        is_js, kind = classify(e.from_address, e.subject)
        prelim.append((e, is_js, kind, is_known_sender(e.from_address)))

    # The job-context threads: any qualifying email anchored by a known sender or
    # an application-shaped kind establishes its thread as job-search (D184).
    job_threads: set[str] = {
        e.thread_id
        for e, is_js, kind, known in prelim
        if is_js and e.thread_id and (known or kind in _ANCHOR_KINDS)
    }

    # Pass 2: gate high-signal verdicts from unknown senders on thread context —
    # an unknown, contextless sender cannot mint the moat's highest cells.
    verdicts: dict[str, str | None] = {}
    by_kind: Counter[str] = Counter()
    for e, is_js, kind, known in prelim:
        if (
            is_js
            and kind in HIGH_SIGNAL_KINDS
            and not known
            and (e.thread_id is None or e.thread_id not in job_threads)
        ):
            is_js, kind = False, None
        verdicts[e.message_id] = kind if is_js else None
        by_kind[kind if is_js else "none"] += 1

    updated = await emails.set_job_search_kinds(
        tenant_context=tenant_context, verdicts=verdicts
    )
    confirmed = sum(v for k, v in by_kind.items() if k != "none")
    return ClassifyResult(
        total=len(rows), confirmed=confirmed, by_kind=dict(by_kind), updated=updated
    )


__all__ = ["ClassifyResult", "classify_job_search_emails"]
