# S102 smoke — the authored CDD layer (D200)

Per-goal LLM-draft + user-proof + provenance. Graph-only (no Postgres change).
Migration `0005_authored_cdd.cypher`; the `:Intermediary`/`:External` node types,
the `:Lever` extension, and the `FEEDS`/`INFLUENCES` edges, all behind the
`TenantScopedNeo4jSession` wrapper.

## Verified this session (code + live, up to the operator's proof gate)

- **Suite green.** `tests/unit` **2304 passed**; `tests/_enforcement` +
  `tests/contract` green; **import-linter 48/0**; AST no-vendor-in-domain +
  no-raw-neo4j green.
- **Migration idempotent on the live graph (AC1).** Applied twice via
  cypher-shell (3 constraints present, no error), then `ops.migrate` applied +
  recorded `0005_authored_cdd` in-container. A throwaway-tenant write/read
  round-trip confirmed the composed-label Cypher (authored lever + `FEEDS`
  edges read back via the coalesce id resolution).
- **AC2 live-verified against Ollama.** The draft use case drafted all **8 live
  goals** through `StructuredOutputPort` (Ollama dev model), zero raw vendor
  imports in domain (the `neo4j-confined` + no-litellm-in-domain contracts
  green). Each goal got **4 levers + 3–4 intermediaries + a coherent expected
  outcome**, persisted `llm_drafted` / `pending`. Get-a-job (sequence) drafted
  as a textbook funnel: levers (Apply / Network / Prepare / Update résumé) →
  intermediaries (Application response rate, Interview invitations, Offer
  acceptance rate) → "Receive a job offer" (the D198 process-stage shape).
- **AC3 tenant isolation (AC6).** The in-container red-team test: tenant A writes
  an authored element; tenant B's read returns none. Every persisted element
  carries `provenance_origin` ∈ {llm_drafted, user_authored, system_suggested},
  `proof_state`, `tenant_id`, `jurisdiction`.
- **AC4 proof paths.** read / accept / correct / reject covered by tests; the
  correct path flips `provenance_origin` to `user_authored`.
- **The proof surface is served (AC5).** `GET /app` carries the List / Map /
  **CDD** toggle (`data-mode="cdd"`); the running image is the freshly re-pinned
  digest (`983b256…`).

## Finding worth recording (reflection 3)

The dev model drafts **levers and intermediaries well** but produced **zero
externals across all 8 goals** — even Get-a-job, where a hiring freeze or a
recruiter's inbound are real externals (D198). The externals dimension is the
weakest of the four; a stronger `model_hint` or a sharper prompt for externals
is named here, not solved here.

Benign: the authored-CDD read logs a Neo4j `UnknownRelationshipTypeWarning` for
`INFLUENCES` until the first external edge exists (no externals were drafted, so
the type is absent). The `FEEDS` edges read correctly; the warning is
informational, not a failure.

## The proof pass is operator-gated (the S101 idiom)

The drafted CDDs are persisted on the live personal-tenant graph and ready to
proof. The live browser proof pass (eyeballing the CDD tab, accept/edit/reject)
is operator-gated — the instance is Google-login wired (no headless backdoor on
the authed corpus). Procedure: open **How am I doing → CDD**, confirm each goal's
drafted CDD reads as something worth proofing (reflection 4), then accept / edit /
reject elements. `make build-api` (never `compose build` alone) advances the
digest pin if a re-pin is needed.
