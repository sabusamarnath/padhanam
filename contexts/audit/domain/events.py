"""AuditEvent value object and hash-chain helpers (D22).

Hash chaining provides tamper-evidence: any insertion or modification breaks
the chain at and after the affected entry, detectable by walk-and-verify.
The chain functions are pure — no I/O, no SDK dependencies — so the domain
stays portable to any adapter.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditEvent:
    """One row in the audit log.

    Schema mirrors D22: actor, tenant_id, jurisdiction, timestamp, action_verb,
    resource_type, resource_id, before/after state, correlation_id, and the
    two hashes that link this event to its predecessor.
    """

    actor: str
    tenant_id: str
    jurisdiction: str
    action_verb: str
    resource_type: str
    resource_id: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    correlation_id: str
    previous_event_hash: str
    this_event_hash: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_event_hash(
    *,
    actor: str,
    tenant_id: str,
    jurisdiction: str,
    timestamp: str,
    action_verb: str,
    resource_type: str,
    resource_id: str,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    correlation_id: str,
    previous_event_hash: str,
) -> str:
    """Hex-encoded SHA-256 of a stable serialization of the event payload + the previous hash.

    Pure function: same inputs → same hash. The hash binds the event to its
    chain position, so any tampering downstream is detectable.
    """
    payload = {
        "actor": actor,
        "tenant_id": tenant_id,
        "jurisdiction": jurisdiction,
        "timestamp": timestamp,
        "action_verb": action_verb,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "before_state": before_state,
        "after_state": after_state,
        "correlation_id": correlation_id,
        "previous_event_hash": previous_event_hash,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainVerificationResult:
    """Result of walking a chain. break_index is the first event whose
    recomputed hash does not match its stored hash, or None for a clean chain.
    """

    is_intact: bool
    break_index: int | None
    length: int


def verify_chain(events: list[AuditEvent]) -> ChainVerificationResult:
    """Walk a chain and return the index of the first break, or clean.

    Pure function: traverses the list, recomputes each event's hash from its
    payload + the previous event's stored hash, and asserts equality.
    """
    expected_prev = GENESIS_HASH
    for idx, event in enumerate(events):
        if event.previous_event_hash != expected_prev:
            return ChainVerificationResult(
                is_intact=False, break_index=idx, length=len(events)
            )
        recomputed = compute_event_hash(
            actor=event.actor,
            tenant_id=event.tenant_id,
            jurisdiction=event.jurisdiction,
            timestamp=event.timestamp,
            action_verb=event.action_verb,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            before_state=event.before_state,
            after_state=event.after_state,
            correlation_id=event.correlation_id,
            previous_event_hash=event.previous_event_hash,
        )
        if recomputed != event.this_event_hash:
            return ChainVerificationResult(
                is_intact=False, break_index=idx, length=len(events)
            )
        expected_prev = event.this_event_hash
    return ChainVerificationResult(
        is_intact=True, break_index=None, length=len(events)
    )
