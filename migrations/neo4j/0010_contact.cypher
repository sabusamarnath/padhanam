// 0010_contact.cypher — the contact graph behind warm access (S103u, D222).
//
// D222 backs warm access with evidence: a :Contact is a person in the operator's
// network, tenant-scoped, keyed by contact_id (like :Opportunity by opportunity_id,
// :Gate by gate_id). A contact links to a company by a normalized company STRING
// (the S103o/D215 company-signature precedent) — not a :Company node, because the
// model carries company as free text everywhere (:Opportunity.name). Contacts are
// seeded system_suggested from the moat senders (read-only) and proofed to
// user_authored; a lead's warm_access derives from whether a usable contact links to
// its company (a read-side projection, D155), the S103t manual tag becoming the
// override (D217).
//
// Statements are auto-committed (DDL cannot run inside a transaction); IF NOT EXISTS
// makes each idempotent, and the :_Migration node gives a file-level idempotency
// check. Statements are separated by a trailing semicolon-newline. Mirrors 0009.

CREATE CONSTRAINT contact_unique_per_tenant IF NOT EXISTS
FOR (c:Contact)
REQUIRE (c.tenant_id, c.contact_id) IS UNIQUE;

CREATE INDEX contact_tenant_id IF NOT EXISTS
FOR (c:Contact)
ON (c.tenant_id);
