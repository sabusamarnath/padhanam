# P15 S56b — Email conversation surface + five-way dispatch (S56 close)

Procedural smoke for the second and final S56 unit: the email conversation
surface reached through the live MetaClassifier dispatch path, the five-way
routing intact (no regression of the prior four), and the D152 Option-A
refresh-before-answer wiring exercised on both branches (success and
fallback).

**Procedural** — operator-shaped, run live against `tenant_a` on the
running stack with working-tree source synced into `padhanam-api`
(`make sync-code`). The smoke is a **wiring-proof**, by design: it proves
routing reaches the email cell and the cell reaches the substrate *only*
through the refresh port. **Volume-path proof and binding sync/refresh
measurement stay open**, gated on a representative inbox at dogfooding
(operator guardrail — the `tenant_a` mailbox is n=1 and unrepresentative;
no sync or refresh architecture is decided on it).

## Prerequisites

- Stack up; `padhanam-api` carrying the S56b working tree (`make sync-code`
  or rebuilt); LiteLLM/Ollama + Nango + Neo4j up; `tenant_a` migration
  0027 applied with the `google-mail` connection present.

## Stage 1 — Five-way routing (live meta-classifier)

Classify one phrasing per surface through the live `LlmMetaClassifierAdapter`
(real LiteLLM/Ollama structured output), including an `email_conversation`
phrasing. Confirm each routes to its surface.

**Record** the routed cell + confidence per phrasing.

## Stage 2 — No-regression spot-check

Confirm the prior four surfaces (manual_entry, audit, mirror, calendar)
still route correctly alongside the new fifth route.

**Record** the routed cell per phrasing.

## Stage 3 — Email cell reached end-to-end (refresh wiring)

Build the `EmailConversationCell` with the live structured-output port, the
real `tenant_a` `PostgresEmailStore` (reader), and the real D152
`build_email_refresh_adapter` (full-pull-in-turn behind the port). Open +
turn an email query and confirm a cited response renders. Exercise both
refresh branches:

- **3a (fallback):** at the cell's default refresh timeout, if the live
  Gmail pull exceeds it, the cell falls back to the cached store and
  carries a staleness note — and still cites directly (D151 cite-directly,
  no snapshot).
- **3b (success):** at a generous timeout, the refresh completes in-turn
  (no staleness note).

The cell imports no `sync_email`; it reaches the substrate **only** through
the `EmailRefreshPort` (D152 boundary).

**Record** the cited-artefact count and the staleness note on both branches.

## Result

Green Stages 1–3 confirm five-way dispatch integration (routing reaches the
email cell, refresh fires through the port on both branches, the response
cites directly), closing S56b and S56. Volume-path + binding refresh
measurement remain deferred to a representative inbox.

## Executed — 2026-06-03 (live, against the running stack)

Run live against `tenant_a` with working-tree source synced into the
running `padhanam-api` container (`make sync-code`) and the real
LiteLLM/Ollama + Nango + Google + Neo4j stack.

- **Stage 1 (five-way routing) — PASS.** The live LLM meta-classifier
  routed `email_conversation` at 0.90 confidence for both
  "What email came in today?" and "Did I get an email from anyone
  important?". The fifth route reaches the email surface live.
- **Stage 2 (no-regression) — PASS.** "Add a data point for Q3 revenue: 5M"
  → `manual_entry` (0.90); "Show me the audit history for the Q3 review
  case" → `audit_conversation` (0.90); "List my open cases" →
  `mirror_conversation` (0.90); "What's on my calendar this week?" →
  `calendar_conversation` (0.90). The fifth route did not regress the prior
  four.
- **Stage 3a (refresh fallback) — PASS.** The email cell, built with the
  live structured-output port + the real `tenant_a` store + the real D152
  refresh adapter, ran open+turn on "what came in recently?". At the
  default refresh timeout the live Gmail pull exceeded it; the cell fell
  back to the cached store and answered with `1` cited email, carrying the
  staleness note "Showing your cached email — the live refresh timed out."
  Cite-directly held (the response carries the email artefact, no
  snapshot). The rendered WhatsApp reply showed the cached email plus the
  staleness warning.
- **Stage 3b (refresh success) — PASS.** Re-run with a 120s refresh
  timeout, the refresh completed in-turn: `staleness_note=None`, `1` cited
  email. Both Option-A branches (success and graceful fallback) are proven
  live; the cell reached the substrate solely through the
  `EmailRefreshPort`.

**Deferred, by design (operator guardrail):** the `tenant_a` mailbox is
n=1, so volume-path behaviour (batched `messages.get`, set-diff deletion at
scale, body chunking throughput) and the binding sync/refresh latency
measurement are NOT proven here and NOT used to decide sync or refresh
architecture. They are gated on a representative inbox at dogfooding —
where the D152 background-sync-vs-incremental decision (currently a pure
wiring swap behind the port) gets its measurement.

**Verdict: all stages green.** Five-way dispatch integration is live
(routing reaches the email cell, refresh fires through the port on both
branches, citations render directly), with no regression of the prior four
surfaces. S56b closes; S56 closes; P15 continues.

**Status: executed live 2026-06-03 (Stages 1–3 green; volume + binding
measurement deferred to a representative inbox).**
