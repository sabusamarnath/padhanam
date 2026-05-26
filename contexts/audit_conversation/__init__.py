"""Audit-conversation bounded context (D138, D139, P14, S51).

The audit-conversation ConversationFlow implementer composes the existing
``AuditEventReader`` port from S36 with the D137 intent-classification
substrate and the D131/D135/D138 response-composition pattern.

Inbound user audit queries classify into typed audit intent value objects
(``FindByCase``, ``FindByDateRange``, ``FindByActor``, ``FindByEventType``,
``FindByCombination``, ``UnclearAuditIntent``); the cell composes the
classified intent into an ``AuditEventListFilters`` DTO, calls the
existing reader, and composes the page into an
``AuditConversationResponse`` value object satisfying the
``CitedResponse`` Protocol from D138.

Per pre-write reconciliation Finding 1 (S51 framing), audit-conversation
consumes the existing ``contexts.audit.ports.reader.AuditEventReader``
rather than introducing a new port; the reader's seven filter dimensions
plus cursor pagination plus chain-integrity verification cover the
query surface audit-conversation needs.

Per pre-write reconciliation Finding 5 (S51 build, option c), the
inbound webhook dispatch decision (which cell handles a given inbound
message) defers to S52 framing when the three-cell topology forces the
question to be answered cleanly. S51 lands the cell at the context
layer with contract-harness registration plus a smoke that exercises
the cell directly; the webhook continues to dispatch to manual_entry_cell
unchanged.
"""
