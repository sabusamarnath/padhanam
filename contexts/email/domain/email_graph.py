"""Email → graph mapping (D151), mirroring calendar's meeting_to_graph.

The structured participants map directly to graph entities/relationships
(no LLM extraction): the sender and each recipient become ``Person``
entities; the sender ``SENT`` and each recipient ``RECEIVED`` the message
(modelled as the message id node? no — kept simple: Person↔Person is not
modelled; the message is the implicit subject). The conservative Phase 2-A
mapping links sender→recipient with a ``CORRESPONDED_WITH`` relationship
so the graph captures who emails whom. Framework-free per D16.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.email.domain.email import Email


@dataclass(frozen=True)
class EmailGraphEntity:
    name: str
    entity_type: str


@dataclass(frozen=True)
class EmailGraphRelationship:
    source_name: str
    source_type: str
    target_name: str
    target_type: str
    relationship_type: str


def email_to_graph(
    email: Email,
) -> tuple[list[EmailGraphEntity], list[EmailGraphRelationship]]:
    """Map an Email's participants to Person entities + correspondence edges."""
    if email.is_deleted:
        return [], []
    participants: list[str] = []
    if email.from_address:
        participants.append(email.from_address)
    for addr in (*email.to_addresses, *email.cc_addresses):
        if addr:
            participants.append(addr)

    seen: set[str] = set()
    entities: list[EmailGraphEntity] = []
    for addr in participants:
        if addr not in seen:
            seen.add(addr)
            entities.append(EmailGraphEntity(name=addr, entity_type="Person"))

    relationships: list[EmailGraphRelationship] = []
    if email.from_address:
        for addr in (*email.to_addresses, *email.cc_addresses):
            if addr and addr != email.from_address:
                relationships.append(
                    EmailGraphRelationship(
                        source_name=email.from_address,
                        source_type="Person",
                        target_name=addr,
                        target_type="Person",
                        relationship_type="CORRESPONDED_WITH",
                    )
                )
    return entities, relationships


__all__ = ["EmailGraphEntity", "EmailGraphRelationship", "email_to_graph"]
