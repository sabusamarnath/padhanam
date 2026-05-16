# Padhanam Architecture

This document is the architectural synthesis surface for Padhanam. It organises architectural commitments into a coherent narrative with diagrams, supporting onboarding-time, phase-audit-time, and procurement-grade-touch reading. It does not duplicate binding rules (`charter/principles.md`) or full reasoning (`charter/decisions.md` plus per-phase archives at `docs/archive/decisions/`); it synthesises them.

## Overview

Padhanam is a public demonstration that a senior product leader can direct the end-to-end implementation of an enterprise-grade agentic platform through Claude Code without writing code (see [`charter/bet.md`](bet.md)). The architectural commitments below exist because the proposition is being tested at the level of complexity that real enterprise software requires: multi-tenant, identity-federated, audit-chained, jurisdiction-aware, OTel-instrumented. A demonstration that AI-assisted development can produce a single-tenant prototype answers nothing useful; the architecture's discipline is the substrate of the proposition.

The platform's substrate (Phase 1, packages P1 through P12) supports an agent layer that demonstrates methodology embedding across professional functions. The four-context P11 substrate scaffold (`contexts/retrieval_evaluation/`, `contexts/run_history/`, `contexts/audit/`, `contexts/optimization/`) is the procurement-grade-defensibility surface that closes the bet's success criterion 4: the trace capture layer surfaces optimisation recommendations procurement readers can verify end-to-end with full evidence-citation traceability.

Architectural decisions read like "what enterprise procurement requires for purchase" — literally so, since enterprise procurement is the level at which the proposition is being tested rather than preparation for a sales motion. The architecture commits to abstractions; protocol choices, vendor selections, and operational specifics are configuration above the abstractions. Vendor lock-in is not architectural per the procurement-grade commitment at `charter/principles.md`.

The seven sections below organise architectural commitments thematically:

1. **Architectural patterns** — hexagonal architecture within a context; bounded contexts at the top of the codebase; observability as foundation; binding specifications live in charter.
2. **Tenancy and jurisdiction** — database-per-tenant; jurisdiction as first-class architectural attribute; tenant onboarding as configuration not deployment; customer-specific behaviour as configuration.
3. **Vendor and dependency posture** — vendor flexibility; LLM-provider-agnostic via LiteLLM; hybrid retrieval; OTel as observability portability boundary; audit hash-chain primitive at platform layer.
4. **Domain primitives** — role-first agent identity; methodology as defaults plus envelopes; four-layer constraint stack; recommendation-shaped optimisation output.
5. **The four-context substrate** — retrieval_evaluation, run_history, audit, ingestion as producers; optimization as consumer; HTTP transport with OpenAPI specification.
6. **Cross-document map** — three-document relationship (principles → decisions → architecture); reading modes; this document's place in the charter.

## Architectural patterns

[Pending in commit 3]

## Tenancy and jurisdiction

[Pending in commit 3]

## Vendor and dependency posture

[Pending in commit 4]

## Domain primitives

[Pending in commit 4]

## The four-context substrate

[Pending in commit 5]

## Cross-document map

Padhanam's charter system uses three documents for three reading modes:

- **`charter/principles.md`** (read every session) — binding rules with D-entry references. Compact prose at session-open. The principles file is the architect's contract: rules that must hold, parenthetical references back to the load-bearing D-entries that committed them. Compact, scannable, present at every session-open per CLAUDE.md's session-start reading order.
- **`charter/decisions.md`** (consult on demand; archived per-phase to `docs/archive/decisions/phase-N.md`) — full Choice / Reasoning / Alternatives / Kano per D-entry. Cold-path audit-time reading. New D-entries in the active phase land in `charter/decisions.md` until phase close, at which point they archive per the methodology document's per-phase archival pattern. Procurement readers verifying any architectural decision against alternatives land here.
- **`charter/architecture.md`** (read at onboarding, phase audits, procurement-grade-touch moments) — architectural synthesis with diagrams. Warm-path synthesis-time reading (this document). Procurement readers, new contributors, and Phase 2 strategic-mode framing read this document for the coherent architectural picture without needing to consult D-entries one at a time.

The three documents serve different reading audiences and different reading moments. They do not duplicate content; they cross-reference. principles.md restates the load-bearing rules with D-entry pointers; decisions.md owns the reasoning behind each rule; architecture.md narrativises the rules and the reasoning together with diagrams that make the structure visible.

Two further charter documents complete the system:

- **`charter/methodology.md`** — the build methodology (how Padhanam itself is built). Distinct from this document, which covers the architecture (what Padhanam is built as). Methodology covers operator discipline, build process, framing-prompt patterns, refactoring conventions, session shapes, measurement model. This document covers the platform's architecture as the artefact the methodology produces.
- **`charter/product-methodology.md`** — the product methodology layer (what the platform encodes for users at the agent layer). Distinct from this document and from `charter/methodology.md`. Product methodology covers the methodology embeddings the agent layer applies across professional functions (Product Management, Marketing, Learning and Development, Project and Programme Management) per `charter/bet.md`.

See `charter/bet.md` for the strategic intent the architecture serves; `charter/prfaq.md` for the external-voice articulation; and `charter/p12-audit-findings.md` for the Phase 1 close architectural verdict.
