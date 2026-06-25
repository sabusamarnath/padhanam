// 0009_measurable_outcome.cypher — the measurable-outcome layer (S103k, D211).
//
// D211 introduces the outcome layer the model lacked: levers/intermediaries/
// externals fed the goal :Outcome node directly, so the intermediaries read as
// endpoints. The five measurable outcomes (Offer received, Offer quality,
// Optionality, Reputation, Relationships) are authored as a new :MeasurableOutcome
// node — keyed by element_id like :Intermediary/:External, NOT by outcome_id, so it
// never collides with the goal :Outcome node (which is keyed by outcome_id; sharing
// the :Outcome label would make every {outcome_id} match hit the elements too). The
// intermediaries FEEDS a :MeasurableOutcome; a :MeasurableOutcome FEEDS the goal
// :Outcome. The authored FEEDS/INFLUENCES edges keep their MERGE idempotency (no
// relationship-property uniqueness in Community Edition), mirroring 0005.
//
// Statements are auto-committed (DDL cannot run inside a transaction); IF NOT EXISTS
// makes each idempotent, and the :_Migration node gives a file-level idempotency
// check. Statements are separated by a trailing semicolon-newline.

CREATE CONSTRAINT measurable_outcome_unique_per_tenant IF NOT EXISTS
FOR (m:MeasurableOutcome)
REQUIRE (m.tenant_id, m.element_id) IS UNIQUE;

CREATE INDEX measurable_outcome_tenant_id IF NOT EXISTS
FOR (m:MeasurableOutcome)
ON (m.tenant_id);
