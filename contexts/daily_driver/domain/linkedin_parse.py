"""Pure parsers for the LinkedIn self-export archive (S103v, D223). Stdlib only
(D16); no vendor SDK, no I/O — the file adapter reads bytes, this parses text.

The archive is the member's own consented data ("Get a copy of your data"), the
route available globally including the UK (the DMA Snapshot API is EEA/Switzerland
only). Two files matter:

- ``Connections.csv`` — first-degree connections. The real **Company** is a column
  (unlike the email seed, where ATS domains hid it). LinkedIn writes a 3-4-line
  "Notes:" preamble before the header row, so the parser finds the header (the row
  carrying "First Name"/"Last Name") and reads from there — header-driven, never by
  position, since columns drift across releases.
- ``messages.csv`` — the ``FROM`` column is the message sender's display name.

Both are tolerant: unknown/extra columns are ignored, headers are matched
case-insensitively, and a missing file yields no contacts (the seed logs the gap).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass


@dataclass(frozen=True)
class LinkedInContact:
    """One parsed LinkedIn person (S103v, D223). ``degree`` is ``first`` for a
    connection, ``None`` for a message-only sender; ``kind`` records which file it
    came from so the seed can weight connections (must-have) over senders."""

    name: str
    company: str | None
    degree: str | None   # "first" for connections, None for message-only senders
    kind: str            # "connection" | "message"


def _norm_key(header: str | None) -> str:
    return (header or "").strip().lstrip("﻿").lower()


def _row(raw: dict) -> dict:
    return {_norm_key(k): (v or "").strip() for k, v in raw.items() if k is not None}


def parse_connections_csv(text: str) -> tuple[LinkedInContact, ...]:
    """First-degree connections, name + company from the export, preamble skipped."""
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "first name" in low and "last name" in low:
            header_idx = i
            break
    if header_idx is None:
        return ()
    reader = csv.DictReader(lines[header_idx:])
    out: list[LinkedInContact] = []
    for raw in reader:
        r = _row(raw)
        name = f"{r.get('first name', '')} {r.get('last name', '')}".strip()
        if not name:
            continue
        company = r.get("company") or None
        out.append(LinkedInContact(
            name=name, company=company, degree="first", kind="connection",
        ))
    return tuple(out)


def parse_messages_csv(text: str) -> tuple[LinkedInContact, ...]:
    """Distinct message senders (the ``FROM`` column), company unknown. Deduped by
    sender name here; the seed dedups these against connections + email contacts."""
    lines = text.splitlines()
    if not lines:
        return ()
    reader = csv.DictReader(lines)
    seen: set[str] = set()
    out: list[LinkedInContact] = []
    for raw in reader:
        r = _row(raw)
        frm = r.get("from", "")
        if not frm:
            continue
        key = frm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(LinkedInContact(
            name=frm, company=None, degree=None, kind="message",
        ))
    return tuple(out)


__all__ = ["LinkedInContact", "parse_connections_csv", "parse_messages_csv"]
