"""index_email — chunk + embed + graph-index a stored Email (D151).

Chunks the Email's subject+body (the email-local chunker), embeds the
chunks via the inherited embedding port, replaces the message's rows in
the email-local chunk store (encrypted text + per-chunk vector), then maps
the participants to graph entities/edges and merges them into the
inherited graph store. No embedding or graph indexing is re-implemented —
only email's chunking, structured mapping, and chunk storage, per the
substrate-inheritance survey.
"""

from __future__ import annotations

from contexts.email.domain.email import Email
from contexts.email.domain.email_chunking import chunk_email
from contexts.email.domain.email_graph import email_to_graph
from contexts.email.ports.email_index_ports import (
    EmailChunkEmbeddingPort,
    EmailGraphIndexPort,
)
from contexts.email.ports.email_repository import EmailChunkRepository
from shared_kernel.tenant_context import TenantContext


async def index_email(
    *,
    tenant_context: TenantContext,
    email: Email,
    embedder: EmailChunkEmbeddingPort,
    graph_index: EmailGraphIndexPort,
    chunks: EmailChunkRepository,
) -> int:
    """Chunk, embed, and graph-index one Email; returns the chunk count."""
    body_chunks = chunk_email(email)
    if body_chunks:
        vectors = await embedder.embed_chunks(
            contents=[c.content for c in body_chunks], tenant_context=tenant_context
        )
        await chunks.replace_chunks(
            tenant_context=tenant_context,
            email_id=email.id,
            message_id=email.message_id,
            chunks=list(zip(body_chunks, vectors, strict=True)),
        )
    entities, relationships = email_to_graph(email)
    if entities or relationships:
        await graph_index.index_email(
            tenant_context=tenant_context,
            entities=entities,
            relationships=relationships,
        )
    return len(body_chunks)


__all__ = ["index_email"]
