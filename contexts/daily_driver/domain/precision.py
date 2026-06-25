"""Matcher precision: the source-class taxonomy and the genuine-match bar (D209).

The matcher (``infer_element_evidence``) produces lexical candidate binds from
titles alone (metadata-light per D16). This module is the use-case-layer filter
that gates each candidate before it persists — the D184 use-case-sees-context
pattern — so non-opportunity and wrong-goal work is not force-fit onto the only
active goal. Two distinct mechanisms, measured separately:

**Mechanism A — the source class** (``source_disposition``). Facet-and-domain
derived: a board listing is market signal, an ATS/application ack is pipeline
volume, neither is an opportunity. Boards and ATS are *allowlists* (bounded, the
D184 lesson — a denylist of newsletters is unbounded and reverse-Kano), and the
application-vs-listing split keys on the subject. Anything the source class cannot
route (internal-facet, a direct thread, an unknown sender) it defers to B.

**Mechanism B — the genuine-match bar** (``is_genuine_bind``). A single *generic*
shared token is not a genuine match. A bind is kept only with a discriminative
token (the read-side honest-why already rates it strong: ``element_token_counts``
<= 1) or two-plus corroborating tokens. This un-binds the incidental-token
mis-links the source class cannot catch — the calendar "warm"-ups, the newsletter
"interview", the ad "offer" — tying the bar to the honest-why (D204).

A unit the source class does not route and that has no genuine bind is **parked**:
left unbound, coverage-honesty (D171/D193) reaching the binding decision. This
module is pure domain; the use case supplies facet metadata and the corpus token
counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from contexts.daily_driver.domain.goal_assessment import (
    ElementEvidence,
    shared_significant_tokens,
    significant_tokens,
)
from contexts.daily_driver.domain.work_unit import FacetType

# Job-board domains (allowlist): listings + application routing, market signal.
BOARD_DOMAINS = frozenset({
    "linkedin.com", "indeed.com", "glassdoor.com", "otta.com",
    "welcometothejungle.com", "totaljobs.com", "reed.co.uk", "cv-library.co.uk",
    "ziprecruiter.com", "jobgether.com", "monster.com", "efinancialcareers.com",
})
# ATS / applicant-tracking platforms (allowlist): application acks + status.
ATS_DOMAINS = frozenset({
    "ashbyhq.com", "myworkday.com", "workday.com", "icims.com", "greenhouse.io",
    "lever.co", "smartrecruiters.com", "workable.com", "teamtailor.com",
    "teamtailor-mail.com", "oraclecloud.com", "oracle.com", "successfactors.com",
    "recruitee.com", "applicant-tracking.com", "eightfold.ai", "ashby.email",
})
FREE_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com",
    "icloud.com", "me.com",
})
# Subject patterns (allowlists): a listing/alert vs an application acknowledgement.
_LISTING_SUBJ = (
    "apply now", "jobs for you", "new jobs", "recommended for you", "and more",
    "jobs matching", "top jobs", "based on your", "job alert", "jobs you may",
)
_APP_ACK_SUBJ = (
    "application was sent", "application was viewed", "received your application",
    "application received", "thank you for applying", "thanks for applying",
    "application has been received", "your job application", "candidate account",
    "received your job application", "application acknowledgement",
    "application update", "received! ", "cv/resume received", "thanks for your interest",
    "application start", "application incomplete", "application outcome",
)

# Source-class dispositions Mechanism A can assign; None defers to Mechanism B.
MARKET = "market"      # board listing -> Labor-market demand external (count)
PIPELINE = "pipeline"  # application ack -> Pipeline-depth intermediary (count)


def _domain_in(domain: str, allowlist: frozenset[str]) -> bool:
    d = (domain or "").lower()
    return any(d == x or d.endswith("." + x) for x in allowlist)


def source_disposition(
    facet_type: FacetType, domain: str, subject: str
) -> str | None:
    """Mechanism A: the source-class route, or ``None`` to defer to the bar.

    An internal facet (task/calendar) always defers — only the genuine-match bar
    separates a real interview block from an unrelated personal item. For an
    email: an application-acknowledgement subject is pipeline volume; a listing/
    alert subject is market signal; an ATS domain with no clear subject is
    pipeline; a board domain with no clear subject is market. A direct/unknown
    sender defers to the bar (it may be a real thread or a newsletter)."""
    if facet_type in (FacetType.TASK, FacetType.MEETING):
        return None
    s = (subject or "").lower()
    if any(p in s for p in _APP_ACK_SUBJ):
        return PIPELINE
    if any(p in s for p in _LISTING_SUBJ):
        return MARKET
    if _domain_in(domain, ATS_DOMAINS):
        return PIPELINE
    if _domain_in(domain, BOARD_DOMAINS):
        return MARKET
    return None


# A single shared token in more than this many of the tenant's units is corpus-
# generic (an "first"/"dose"-class word) even if it is rare among element labels,
# so it is not a genuine match on its own. Separates "acme" (~5 units) from
# "first" (~120 medication units).
CORPUS_GENERIC_THRESHOLD = 10


def is_genuine_bind(
    unit_titles: tuple[str, ...],
    element_label: str,
    token_element_counts: dict[str, int],
    unit_token_counts: dict[str, int] | None = None,
) -> bool:
    """Mechanism B: is this keyword/alias bind a genuine match? Kept with two-plus
    corroborating shared tokens, or a single token that is **both** discriminative
    among element labels (the honest-why's STRONG, ``token_element_counts`` <= 1)
    **and** not corpus-generic (in <= ``CORPUS_GENERIC_THRESHOLD`` of the tenant's
    units — the IDF refinement that catches an element-rare but corpus-common token
    like "first"). A single generic token is not a match. Exact-tier binds are
    genuine by construction and never reach here."""
    shared: set[str] = set()
    for t in unit_titles:
        shared |= shared_significant_tokens(t, element_label)
    if len(shared) >= 2:
        return True
    if len(shared) == 1:
        tok = next(iter(shared))
        if token_element_counts.get(tok, 1) > 1:
            return False
        if unit_token_counts is not None and (
            unit_token_counts.get(tok, 0) > CORPUS_GENERIC_THRESHOLD
        ):
            return False
        return True
    return False


@dataclass(frozen=True)
class UnitSource:
    """The facet metadata the precision filter reads for one unit (D209). The use
    case assembles it from the unit's primary facet (an email's sender domain +
    thread size, or the internal-facet type) — the matcher domain stays
    title-only (D16)."""

    facet_type: FacetType
    domain: str
    subject: str
    thread_size: int
    titles: tuple[str, ...]


@dataclass(frozen=True)
class PrecisionResult:
    """The filtered evidence plus each mechanism's contribution (D209), so the
    re-measure can report the split."""

    kept: tuple[ElementEvidence, ...]
    market_units: frozenset[UUID]     # routed to the Labor-market external (count)
    pipeline_units: frozenset[UUID]   # routed to Pipeline-depth (count)
    parked_units: frozenset[UUID]     # un-bound by the bar — no genuine match
    protected_units: frozenset[UUID]  # confirmed/clustered, exempt from filtering


def apply_precision(
    evidence: tuple[ElementEvidence, ...],
    *,
    unit_source: dict[UUID, UnitSource],
    element_label_by_id: dict[UUID, str],
    token_element_counts: dict[str, int],
    protected_unit_ids: frozenset[UUID],
    unit_token_counts: dict[str, int] | None = None,
) -> PrecisionResult:
    """Gate the lexical candidate binds (D209). Per unit: a protected unit
    (rule-confirmed job email or a clustered opportunity unit) is kept untouched;
    a source-class route (market/pipeline) drops the unit's binds and counts it;
    otherwise the genuine-match bar keeps only the unit's genuine binds, and a
    unit left with none is parked. Exact-tier binds are always genuine."""
    by_unit: dict[UUID, list[ElementEvidence]] = {}
    order: list[UUID] = []
    for ev in evidence:
        if ev.unit_id not in by_unit:
            by_unit[ev.unit_id] = []
            order.append(ev.unit_id)
        by_unit[ev.unit_id].append(ev)

    kept: list[ElementEvidence] = []
    market: set[UUID] = set()
    pipeline: set[UUID] = set()
    parked: set[UUID] = set()
    for unit_id in order:
        binds = by_unit[unit_id]
        if unit_id in protected_unit_ids:
            kept.extend(binds)
            continue
        src = unit_source.get(unit_id)
        if src is not None:
            disp = source_disposition(src.facet_type, src.domain, src.subject)
            if disp == MARKET:
                market.add(unit_id)
                continue
            if disp == PIPELINE:
                pipeline.add(unit_id)
                continue
        titles = src.titles if src is not None else ()
        # The bar gates only the element keyword tier; an exact match is genuine
        # by construction, and the alias (goal-name) fallback is the legacy recall
        # the single-signal suppression policy governs separately (D186), kept
        # orthogonal here.
        genuine = [
            b for b in binds
            if b.tier in ("lexical_exact", "alias")
            or is_genuine_bind(
                titles, element_label_by_id.get(b.element_id, ""),
                token_element_counts, unit_token_counts,
            )
        ]
        if genuine:
            kept.extend(genuine)
        else:
            parked.add(unit_id)
    return PrecisionResult(
        kept=tuple(kept),
        market_units=frozenset(market),
        pipeline_units=frozenset(pipeline),
        parked_units=frozenset(parked),
        protected_units=protected_unit_ids,
    )


__all__ = [
    "ATS_DOMAINS",
    "BOARD_DOMAINS",
    "FREE_DOMAINS",
    "MARKET",
    "PIPELINE",
    "PrecisionResult",
    "UnitSource",
    "apply_precision",
    "is_genuine_bind",
    "source_disposition",
]
