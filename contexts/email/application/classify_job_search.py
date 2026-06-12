"""classify_job_search use case — label the stored emails (D183, S89).

Reads the live emails (decrypted sender + subject), runs the rules-only
classifier (domain), and **persists** each verdict on the email row
(``job_search_kind``) so ``correlate_goal_facets`` re-reads it on every
recompute and the Get-a-job SERVES edges stay durable. Idempotent — re-running
after tightening the rules overwrites the column, so the edges follow the rules.
Counts only; no senders/subjects leave the process.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from contexts.email.domain.email import Email
from contexts.email.domain.job_search_classifier import classify
from shared_kernel import TenantContext


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
    verdicts: dict[str, str | None] = {}
    by_kind: Counter[str] = Counter()
    for e in rows:
        is_js, kind = classify(e.from_address, e.subject)
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
