"""Calendar bounded context (D148).

The Phase 2-A P15 calendar data substrate (S55a): pull calendar events
through self-hosted Nango's Proxy per D14's separate-service pattern,
store each event as a ``Meeting`` artefact in the tenant store keyed on
its stable Google event id (a mutable search cache: deltas upsert
modified events and tombstone cancelled ones), and index it into the
inherited hybrid-retrieval substrate so search runs locally rather than
re-querying Google.

Hexagonal layers within: ``domain`` / ``ports`` / ``application`` /
``adapters``. No Google or Nango specifics appear in domain code; all of
it sits behind the calendar port and the single Nango Proxy adapter
(no-vendor-SDK-in-domain). The calendar-conversation surface, the
MetaClassifier extension, the gold sets, and the citation-time
audit-snapshot wiring are S55b, not built here.
"""
