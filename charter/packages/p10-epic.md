# P10 Epic — Audit log viewer (backend-only)

## Retrospective addendum (S38 close, 2026-05-14)

P10 closed at S38 close on 2026-05-14 with three sessions shipped:
S36 (audit context read substrate — `AuditEventReader` consumer-
defined port, Postgres adapter against both destinations, chain
integrity verifier reusing the existing hash primitives,
intra-context port-location asymmetry recorded as carryover), S37
(HTTP transport for the audit reader at two route trees + D23
backend extension with the platform-operator principal type +
parallel `register_audit_error_handlers` registration shape per
finding-4 resolution), and S38 (auth error handler relocation to a
new cross-cutting `_auth_errors.py` module + HTTP API for ingestion
management consuming the existing application layer via Path A + P10
close end-to-end demo). Three D-entries landed across the package:
D102 (P10 framing — read port shape, two-destination model, chain
integrity verification on read at page granularity, ingestion-
management API absorbed from the P6 carryover), D103 (platform-
operator principal type as discriminator-field claim + HTTP
transport with two route trees + 403 path extension), D104 (auth
error handler cross-cutting registration + ingestion HTTP transport
with three read routes via Path A — extend `SourceRepositoryPort`
with `list_sources` plus add a `list_sources` application use case
rather than stand up a separate consumer-defined reader port).

**Delta from framing.** The framing forecast three-to-four sessions;
as-built shipped three. S39 carryover hygiene did not need a
session because no carryover surfaced at S38 close. The
`PrincipalTypeMismatchError` handler-location entry the S38 brief
expected in `charter/deferred-decisions.md` did not exist as a
separate entry; the architectural seed was at D103 alternative (i)
("preserves the option to refactor to a generic
`register_error_handlers` at a future cleanup moment"). The
relocation at S38 commit 2 still proceeded per the architectural
intent and the trigger fired exactly as the alternative (i)
language anticipated. The audit-context port-location asymmetry
carryover from S36 (write-side `AuditPort` at
`contexts/audit/domain/ports.py`; read-side `AuditEventReader` at
`contexts/audit/ports/reader.py`) stays open and inherits to the
next port added to the audit context per the existing
`charter/current-package.md` "Carryovers active across the P8→P9
boundary" entry.

**Substrate as Phase 2 UX consumer surface.** P10 closes with the
full audit and ingestion management read substrate in place: the
consumer-defined audit reader port (S36) with chain integrity
verification at page granularity reusing the existing
`compute_event_hash` and `GENESIS_HASH` primitives; the HTTP
transports for both destinations under separate principal-derived
gating (S37); the principal-type discriminator separating
tenant-typed and platform-operator-typed access at the token
chokepoint (S37); the cross-cutting auth error handler at
`_auth_errors.py` so future routers consuming the shared
`get_tenant_context` chokepoint inherit the 403 path without
coupling to audit (S38); the ingestion management API with three
read routes consuming the existing application layer via Path A
(S38). Every consumer surface Phase 2 UX needs for audit-evidence
and ingestion-management observability is in place and verifiable
end-to-end through a single reproducible script at
`scripts/smoke_p10_s38.py`.

**Phase 1 substrate-completeness observations recorded at S38
close.** Three observations surface from the P10 close demo at
`docs/smoke/p10_s38_close_demo.md` for the Phase 1 close audit at
P12. First, the audit-context port-location asymmetry from S36
inherits unchanged through P10 close — the next port added to the
audit context (likely at P11 recommendation-engine consumers if it
needs audit reads, or a Phase 2 surface) will activate the
symmetrize-or-accept decision. Second, the chain integrity
verifier returns `partial` rather than `verified` on a single-row
page — this is the correct page-granularity-verifier shape per
D102's `partial` semantics, but the smoke surfaced it as a
structurally honest "I cannot verify two-row chain links on a
one-row page" rather than a false-positive `verified`; the
observation is recorded so the Phase 2 UX audit-viewer designer
understands the three-state surface from day one. Third, the
trace-id propagation gap from P9 close did not surface during the
P10 read paths because the HTTP layer does not yet read or
display `trace_id`; the gap remains open for the Phase 1 close
audit per the P9 retrospective.

**Methodology candidate reinforcements at P10.** Pre-write
reconciliation reinforced at session-open for all three P10
sessions — S36 (one structural-honesty finding on audit port
location resolving to operator-selected option A), S37 (one
structural-honesty finding on the platform-operator-versus-roles
relationship resolving via D103 alternative (b)), S38 (one
structural-honesty finding on the missing `list_sources` capability
resolving to operator-selected Path A). Each pre-write
reconciliation produced one D-entry alternative revision that
shaped the final commitment. The pattern reached an inferred 16
instances at S37 close and 17 at S38 close — the methodology
candidate count continues to grow at a stable rate (one per build
session) and the substrate-extension-time variant (catching brief-
versus-built-state mismatches rather than architectural-drift
mismatches) shows up across P10 as the pre-write reconciliation
mode shifts when the codebase is in extension rather than
shape-establishing mode.

Consumer-port-plus-wiring-adapter reinforced at S36 (the tenth
class on `apps/cli/_cross_context.py`, `AuditEventReaderAdapter`)
and at S38 in a sub-shape variant — the `TenantRoutingSourceRepository`
at `apps/api/_agent_runtime_wiring.py` is a routing-wrapper rather
than a port-defined-elsewhere-wired-here adapter, but it follows
the same shape: the production composition layer owns the
per-tenant routing impedance, the consumer (the HTTP route) sees
a single clean port surface. Both forwarded as methodology
candidates for the Phase 1 close audit at P12 close per the
build-versus-strategic discipline (D47).

**Architectural-extension-rather-than-greenfield as a P10
characteristic.** P10 differed from earlier packages in that every
S36/S37/S38 session extended an existing bounded context rather
than shaping a new one. The reconciliation-as-discovery shape
shifted accordingly: S36 reconciled where to place a new port
within the existing audit context (intra-context placement
question rather than cross-context architecture question); S37
reconciled how to extend the existing D23 token model rather than
replace it; S38 reconciled whether to extend the existing
`SourceRepositoryPort` (Path A) or stand up a parallel reader port
(Path B). All three reconciliations produced cleaner outcomes
because the existing context shape constrained the option set.
Worth noting at the Phase 1 close audit: P10's reconciliation
mode tracks the codebase's maturity arc — early packages
established context boundaries, P10 extends them, and Phase 2
will exercise them.

## Goal

P10 ships the audit log read substrate that closes Phase 1's
audit-evidence claim per D92 and that Phase 2 trust-and-evidence
UX consumes directly per D93. At P10 close, every audit row
written since P3 across both destinations (per-tenant hash chains
and the control-plane registry chain) is queryable through a
consumer-defined read port; the read surface verifies chain
integrity on read so the bet's hash-chained-audit claim has a
working artefact behind it; the HTTP transport exposes both
destinations through separately authorized routes; and the
deferred HTTP API for ingestion management absorbed from the P6
carryover lands inside P10 alongside the audit surface as the
second admin-grade Phase 2 substrate.

## Scope at P10 close

The existing `contexts/audit/` bounded context extends with the
read side. The write side from P3 stays unchanged; P10 adds the
consumer-defined query port, the Postgres adapter against both
destinations, the HTTP transport, and chain-integrity
verification at read time.

Two read destinations: the per-tenant `tenant_audit` table on
each tenant's data plane (writing since S11), and the
control-plane `tenant_audit` table on the dedicated
control-plane Postgres instance (writing since S12). Both share
schema column-for-column at 13 columns including `id` (UUID
primary key, server-generated via `gen_random_uuid()`); both
share the hash-chain primitives at
`contexts/audit/domain/events.py`; both are queried through the
same port with destination as a parameter on the port methods.

The read port surfaces three reads at framing forecast:
`get_audit_event` returning a single event by id,
`list_audit_events_with_filters` returning a paginated filtered
list under cursor pagination, and `verify_chain_segment`
returning chain-integrity status for a page of returned rows.
The cursor codec mirrors the P9 base64-of-JSON shape and
paginates on `(timestamp, id)` with `DESC, DESC` sort. Filter
vocabulary covers time window, actor, action verb, resource_type,
resource_id, correlation_id, and jurisdiction. The `resource_id`
filter is only valid when `resource_type` is also supplied;
absent that, the query layer returns a validation error.

Chain integrity verifies on read. Each returned page carries a
`chain_integrity` field surfacing one of: `verified` (every
row's `this_event_hash` recomputes from payload plus
`previous_event_hash` and the chain links match across the
page), `broken_at_row` (specific row failed verification),
`partial` (page span did not cover a chain segment large enough
to verify, for example when filters skip rows). The hash
recomputation reuses `compute_event_hash` and `GENESIS_HASH`
from `contexts/audit/domain/events.py` as primitives;
`verify_chain` (the existing from-genesis walker) is NOT reused
because the read-side page may start mid-chain. The
page-granularity verifier is structurally new logic on top of
the reusable primitives. Full-chain verification across the
entire chain end-to-end is out of scope and deferred to Phase 2
or operator-evidence-triggered, whichever comes first.

HTTP routes land at `apps/api/routers/audit.py`. Two route
prefixes: `/audit` for the per-tenant chain, served under the
existing principal-derived tenant context pattern from S29b and
S34; `/platform/audit` for the control-plane chain, served
under a new platform-operator principal type added to the D23
signed-token backend. Error response shape inherits S34's
eleven-path map. Both routes carry correlation-id round-trip.

The D23 signed-token backend extends with a platform-operator
claim. The dependency function that resolves principals to query
contexts gains a second branch: platform-operator principals
route to control-plane scope rather than a tenant-derived
context. Browser-based session handling at Phase 1 close
inherits the claim model unchanged; only login flow changes.

The HTTP API for ingestion management absorbs from the P6
deferred carryover and lands inside P10. The API surface exposes
existing ingestion use cases at `contexts/ingestion/application/`
over FastAPI routes following the principal-derived tenant
context convention. The minimum useful set: list sources, get
source by id, get source ingestion status. Upload over HTTP and
reindex stay CLI-only at Phase 1 close unless build evidence
pulls them in.

Tenant-isolation contract tests extend the existing
`tests/contract/tenant_isolation/` harness to cover the audit
read paths and the ingestion management routes. Cross-tenant
read attempts through both surfaces must fail. Cross-destination
attempts (a tenant principal trying to read the control-plane
chain via the per-tenant route or vice versa) must fail with
the appropriate isolation response.

## Sessions forecast

Three sessions most likely, possibly four. Session boundaries
settle session-by-session per the established discipline.
Indicative shape:

- **S36:** `contexts/audit/` extends with the read side.
  `AuditEventReader` port, domain value objects, Postgres
  adapter against both destinations, wiring at both composition
  roots, contract-harness extensions, live-stack smoke. D-entry
  forecast: concrete read-port shape, filter vocabulary,
  chain-integrity status shape.
- **S37:** HTTP routes for the audit reader at
  `apps/api/routers/audit.py`. Two route trees, `/audit` and
  `/platform/audit`. D23 extends with the platform-operator
  claim. Dependency resolver branches on principal type. D-entry
  forecast: HTTP DTO shape, query-string vocabulary,
  platform-operator claim semantics.
- **S38:** HTTP API for ingestion management at
  `apps/api/routers/ingestion.py`. End-to-end demonstration. P10
  retrospective and archive per the P8 and P9 precedent.
  D-entry forecast: ingestion management HTTP endpoint shape.
- **S39** if needed lands carryover hygiene or a deferred
  close. Build evidence at S38 close settles.

## D-entries forecast

Three to four D-entries across the package. Forecast at framing:

- Read-port shape at S36.
- HTTP transport at S37 including the platform-operator claim.
- Ingestion management HTTP endpoint shape at S38.
- Possibly: a Kano-recorded decision on full-chain verification
  deferral if it surfaces structurally at build.

## Out of scope

- **Full-chain verification endpoint.** Deferred to Phase 2 or
  operator-evidence-triggered. Page-level chain integrity
  verification on read is must-have; the end-to-end walk is
  delighter.
- **Audit log UI (tenant operator view, compliance operator
  view).** Deferred to Phase 2 per D92.
- **Audit search by hash directly.** Available as degenerate
  case of the filter vocabulary if needed; not a first-class
  endpoint at P10.
- **Audit-driven recommendation in the optimization layer.** P11
  territory.
- **HTTP API for evaluation management.** P11 per the
  carryover-routing settled at P10 framing.
- **HTTP upload of new sources via the ingestion management
  API.** CLI-only at Phase 1 close unless build evidence pulls
  it in.
- **Browser-based authentication.** Phase 1 close
  substrate-completion territory; D23's signed-token backend
  with the platform-operator claim is the Phase 1 mechanism.

## Open questions surfaced at framing

- Exact filter vocabulary settles at S36 against the seven
  framing candidates.
- `ChainIntegrityStatus` shape settles at S36 (page-level versus
  row-level granularity, what `partial` means concretely).
- Whether the ingestion management API ships read-only at S38
  or absorbs upload-over-HTTP.
- Whether S39 lands carryover hygiene or stays unused.
