// 0011_skills_profile.cypher — the operator skills profile (S103af, D238).
//
// D238 (matching-engine leg 2): a :SkillItem is one entry in the operator's standing
// skills profile extracted from their CV — read by every opportunity, not per-
// opportunity data. Tenant-scoped, keyed by item_id (like :Contact by contact_id,
// :Opportunity by opportunity_id). Properties (kind, text, proof_state,
// provenance_origin) are schemaless — no constraint needed on them. A CvExtractorPort
// (over the D236 StructuredOutputPort seam) drafts items proof_state='suggested';
// only the operator's confirm promotes to 'confirmed' (the extract-and-proof lifecycle,
// D215/D222). Leg 3 reads the confirmed profile against the D228 selection criteria to
// feed the D221 fit tier.
//
// Statements are auto-committed (DDL cannot run inside a transaction); IF NOT EXISTS
// makes each idempotent, and the :_Migration node gives a file-level idempotency
// check. Statements are separated by a trailing semicolon-newline. Mirrors 0010.

CREATE CONSTRAINT skill_item_unique_per_tenant IF NOT EXISTS
FOR (s:SkillItem)
REQUIRE (s.tenant_id, s.item_id) IS UNIQUE;

CREATE INDEX skill_item_tenant_id IF NOT EXISTS
FOR (s:SkillItem)
ON (s.tenant_id);
