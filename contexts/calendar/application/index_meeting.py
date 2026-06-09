"""index_meeting — embed + graph-index a stored Meeting (D148, survey).

Synthesises the Meeting to text and embeds it via the inherited embedding
capability, writes the vector onto the calendar-owned meetings row, then
maps the structured fields to graph entities/relationships and merges them
into the inherited graph store. No embedding or graph indexing is
re-implemented here — only calendar's synthesis, structured mapping, and
vector storage, per the substrate-inheritance survey.
"""

from __future__ import annotations

from contexts.calendar.domain.meeting import Meeting
from contexts.calendar.domain.meeting_graph import meeting_to_graph
from contexts.calendar.ports.meeting_index_ports import (
    MeetingEmbeddingPort,
    MeetingGraphIndexPort,
)
from contexts.calendar.ports.meeting_repository import MeetingRepository
from shared_kernel.tenant_context import TenantContext


async def index_meeting(
    *,
    tenant_context: TenantContext,
    meeting: Meeting,
    embedder: MeetingEmbeddingPort,
    graph_index: MeetingGraphIndexPort,
    meetings: MeetingRepository,
) -> None:
    text = meeting.to_search_text()
    if text.strip():
        vector = await embedder.embed(text=text, tenant_context=tenant_context)
        await meetings.set_embedding(
            tenant_context=tenant_context,
            calendar_id=meeting.calendar_id,
            google_event_id=meeting.google_event_id,
            vector=vector,
        )
    entities, relationships = meeting_to_graph(meeting)
    if entities or relationships:
        await graph_index.index_meeting(
            tenant_context=tenant_context,
            entities=entities,
            relationships=relationships,
        )


__all__ = ["index_meeting"]
