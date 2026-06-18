# S103c smoke — editability and the learning signal (D203)

Relink, unlink, capture, and a re-runnable correction-respecting re-match. No
migration (the `user_owned` :Unit marker and the corrections-as-audit-events are
schemaless over the `0005`/`0006` shapes).

## Verified this session (code + live on real Neo4j)

- **Suite green.** `tests/unit` passes; `tests/_enforcement` green; **import-linter
  48/0** (the `daily_driver.application → contexts.audit.domain` correction-emit is
  the optimization-precedented application-layer sink).
- **Live contract guards (5/5).** `test_correction_isolation` proves on real Neo4j:
  tenant A relinks a unit (the edge moves, the unit is marked `user_owned`), a
  re-match-shaped delete (`replace_element_evidence([])`) **keeps the user-owned
  unit's edge and drops the non-owned unit's** (correction precedence), and tenant
  B reads none. The S103b element-evidence + authored-CDD guards still pass.
- **Re-match idempotent on the live corpus (AC3).** Re-running `make
  correlate-units` produced **847 EVIDENCES again** (stable), `SERVES = 0`,
  `user_owned = 0` — no duplicates, no change to correct bindings (no corrections
  made headlessly; the personal authored model is left for the operator).
- **The interactive lens is served (AC6).** The rebuilt image (`bc1de6b`) serves
  the CDD lens with the **Re-match** trigger, the per-element "N units ▾" expand
  into bound units, and **Relink/Unlink** affordances (`grep` of the served HTML).

## Capture (the learning signal)

Each relink/unlink emits an append-only **correction audit event**
(`cdd.relink` / `cdd.unlink`, `before_state` the prior binding, `after_state` the
new binding) through `AuditPort.emit` — the canonical hash-chained record AND the
learning signal a later session reads back through the audit reader's faceted
query. Verified at the unit level (the emit + provenance); the live audit-Postgres
write is the audit adapter's own tested path.

## Operator-gated

The three reflections (correction rate by element type; coverage recovery after
authoring a missing goal and re-matching; whether unit-level ownership bit) need
the operator's interactive corrections on the real corpus — the browser pass. The
tools are delivered, served, and live-guarded; `make build-api` advanced the pin
to `bc1de6b`. Authoring a missing recurring goal (e.g. Esperanto, surfaced unbound
at S103b) and clicking **Re-match** is the coverage-recovery workflow this session
exists to enable.
