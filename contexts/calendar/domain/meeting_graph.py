"""Meeting -> graph mapping (D148, substrate-inheritance survey).

A Meeting's entities are already structured, so calendar maps them
directly to graph entities and relationships rather than running
ingestion's LLM ``entity_extractor_port``. The graph *store* is inherited
(ingestion's GraphRepositoryPort, same Neo4j, tenant-scoped MERGE); only
this structured mapping is calendar's. Framework-free per D16 — these are
plain value objects the consumer port carries; the apps/ wiring bridge
translates them to ingestion's Entity/Relationship.
"""

from __future__ import annotations

from dataclasses import dataclass

from contexts.calendar.domain.meeting import Meeting

ENTITY_PERSON = "Person"
ENTITY_PLACE = "Place"
ENTITY_MEETING = "Meeting"

REL_ORGANIZED = "ORGANIZED"
REL_ATTENDED = "ATTENDED"
REL_LOCATED_AT = "LOCATED_AT"


@dataclass(frozen=True)
class MeetingGraphEntity:
    name: str
    entity_type: str


@dataclass(frozen=True)
class MeetingGraphRelationship:
    source_name: str
    source_type: str
    target_name: str
    target_type: str
    relationship_type: str


def meeting_to_graph(
    meeting: Meeting,
) -> tuple[tuple[MeetingGraphEntity, ...], tuple[MeetingGraphRelationship, ...]]:
    """Map a Meeting's structured fields to graph entities + relationships.

    The Meeting itself is a node; the organizer and attendees are Person
    nodes; the location is a Place node. Relationships connect them. A
    cancelled or empty Meeting yields nothing (no content to index).
    """
    meeting_name = meeting.title or f"Meeting {meeting.google_event_id}"
    if meeting.is_cancelled:
        return (), ()

    entities: list[MeetingGraphEntity] = [
        MeetingGraphEntity(name=meeting_name, entity_type=ENTITY_MEETING)
    ]
    relationships: list[MeetingGraphRelationship] = []

    if meeting.organizer_email:
        entities.append(
            MeetingGraphEntity(
                name=meeting.organizer_email, entity_type=ENTITY_PERSON
            )
        )
        relationships.append(
            MeetingGraphRelationship(
                source_name=meeting.organizer_email,
                source_type=ENTITY_PERSON,
                target_name=meeting_name,
                target_type=ENTITY_MEETING,
                relationship_type=REL_ORGANIZED,
            )
        )

    for attendee in meeting.attendees:
        label = attendee.display_name or attendee.email
        if not label:
            continue
        entities.append(
            MeetingGraphEntity(name=label, entity_type=ENTITY_PERSON)
        )
        relationships.append(
            MeetingGraphRelationship(
                source_name=label,
                source_type=ENTITY_PERSON,
                target_name=meeting_name,
                target_type=ENTITY_MEETING,
                relationship_type=REL_ATTENDED,
            )
        )

    if meeting.location:
        entities.append(
            MeetingGraphEntity(name=meeting.location, entity_type=ENTITY_PLACE)
        )
        relationships.append(
            MeetingGraphRelationship(
                source_name=meeting_name,
                source_type=ENTITY_MEETING,
                target_name=meeting.location,
                target_type=ENTITY_PLACE,
                relationship_type=REL_LOCATED_AT,
            )
        )

    # De-duplicate entities by (name, type) while preserving order.
    seen: set[tuple[str, str]] = set()
    unique_entities: list[MeetingGraphEntity] = []
    for ent in entities:
        key = (ent.name, ent.entity_type)
        if key not in seen:
            seen.add(key)
            unique_entities.append(ent)

    return tuple(unique_entities), tuple(relationships)
