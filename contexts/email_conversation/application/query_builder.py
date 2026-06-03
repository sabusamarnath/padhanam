"""Query builder — filter the email store by a typed email intent (D151, S56b).

The EmailReader exposes ``list_emails`` (the tenant's stored, non-deleted
emails, newest received first); the cell filters that list in memory by
the resolved intent. Pure functions on ``Email`` value objects. Mirrors
the calendar query builder; date-window resolution is UTC-anchored and
deterministic.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from contexts.email.domain.email import Email

_SUBJECT_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "a", "an", "my", "our", "this", "that", "these", "those",
        "to", "of", "for", "in", "on", "and", "or", "with", "about",
        "email", "emails", "message", "messages", "mail", "thread", "re", "fwd",
    }
)


def _day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def resolve_window(range_keyword: str, *, now: datetime) -> tuple[datetime, datetime]:
    """Resolve a relative range keyword to a concrete [start, end) UTC window."""
    now = now.astimezone(timezone.utc)
    today_start, today_end = _day_bounds(now)
    if range_keyword == "today":
        return today_start, today_end
    if range_keyword == "yesterday":
        return today_start - timedelta(days=1), today_start
    if range_keyword == "this_week":
        monday = today_start - timedelta(days=now.weekday())
        return monday, monday + timedelta(days=7)
    if range_keyword == "last_week":
        monday = today_start - timedelta(days=now.weekday())
        return monday - timedelta(days=7), monday
    if range_keyword == "this_month":
        first = today_start.replace(day=1)
        nxt = first.replace(year=first.year + 1, month=1) if first.month == 12 else first.replace(month=first.month + 1)
        return first, nxt
    raise ValueError(f"unknown range_keyword {range_keyword!r}")


def _received_sorted(emails: tuple[Email, ...]) -> list[Email]:
    live = [e for e in emails if not e.is_deleted and e.received_at is not None]
    live.sort(key=lambda e: e.received_at, reverse=True)  # type: ignore[arg-type,return-value]
    return live


def emails_in_window(
    emails: tuple[Email, ...], *, start: datetime, end: datetime
) -> tuple[Email, ...]:
    return tuple(
        e for e in _received_sorted(emails)
        if start <= e.received_at.astimezone(timezone.utc) < end  # type: ignore[union-attr]
    )


def emails_from_sender(emails: tuple[Email, ...], *, sender: str) -> tuple[Email, ...]:
    needle = sender.strip().lower()
    if not needle:
        return ()
    return tuple(
        e for e in _received_sorted(emails)
        if (e.from_address and needle in e.from_address.lower())
        or any(needle in a.lower() for a in (*e.to_addresses, *e.cc_addresses))
    )


def recent_emails(emails: tuple[Email, ...], *, limit: int) -> tuple[Email, ...]:
    return tuple(_received_sorted(emails)[:limit])


def subject_tokens(text: str) -> frozenset[str]:
    return frozenset(
        word for word in re.split(r"[^a-z0-9]+", text.lower())
        if word and word not in _SUBJECT_STOPWORDS
    )


def resolve_subject_reference(
    reference: str, emails: tuple[Email, ...]
) -> tuple[Email | None, tuple[Email, ...]]:
    """Resolve a natural-language subject reference; mirrors calendar's title resolver.

    Returns ``(matched, ())`` on a unique best match; ``(None, candidates)`` on a
    multi-match tie (D139 resolution-ambiguity); ``(None, ())`` on no match.
    """
    ref = subject_tokens(reference)
    candidates = [e for e in emails if not e.is_deleted and e.subject]
    if not ref or not candidates:
        return None, ()
    exact = [e for e in candidates if subject_tokens(e.subject or "") == ref]
    if len(exact) == 1:
        return exact[0], ()
    scored = [(len(ref & subject_tokens(e.subject or "")), e) for e in candidates]
    best = max(s for s, _ in scored)
    if best == 0:
        return None, ()
    winners = tuple(e for s, e in scored if s == best)
    if len(winners) == 1:
        return winners[0], ()
    return None, winners


__all__ = [
    "emails_from_sender",
    "emails_in_window",
    "recent_emails",
    "resolve_subject_reference",
    "resolve_window",
    "subject_tokens",
]
