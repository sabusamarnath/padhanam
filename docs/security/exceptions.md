# Security exceptions

Documented exceptions to the strict-by-default policy in
[`checklist.md`](checklist.md). Each exception names a category, the
rationale, and the next review date. Specific CVE IDs live in
[`.trivyignore`](../../.trivyignore) at the repo root; the categories below
map every entry there to a justification.

The categories are intentionally coarse. Per-CVE rationale is not
load-bearing here — what matters is that the operator has decided which
classes of finding are accepted at the dev-stack stage and what mechanism
re-evaluates them.

## Active exception categories

### A. Base-image transitive CVEs — OS packages

**Scope:** Findings in OS packages (libc, libssl, ncurses, openldap, sqlite,
zlib, libgcrypt, libsystemd, etc.) inside the upstream container images we
pin in `compose.yaml`. Examples: `CVE-2026-31789`, `CVE-2025-7458`,
`CVE-2026-0861`.

**Rationale:** These findings are in transitive OS packages of upstream
images we have pinned to a digest. We do not rebuild those images; the
correct response is to take a digest bump from the upstream when a fixed
image is published. Pinning is what gives us an explicit upgrade decision;
the monthly digest-bump check (D25, see
[`scheduled-checks.md`](scheduled-checks.md)) is what re-evaluates this
class of exception.

**Affects:** pgvector/pgvector:pg17, postgres:17-alpine, redis:7-alpine,
caddy:2-alpine, clickhouse/clickhouse-server:24.12,
langfuse/langfuse:3.172.0, langfuse/langfuse-worker:3.172.0.

**Review date:** 2026-05-29 (first monthly digest check).

### B. Base-image transitive CVEs — Go stdlib in vendor binaries

**Scope:** Findings in `stdlib` from vendored Go binaries (`gosu`, image
build tools, the Ollama daemon binary) inside upstream images. Examples:
`CVE-2025-68121`, `CVE-2026-25679`, `CVE-2025-22874`, `CVE-2026-32285`,
the long Go-1.18-era list (`CVE-2022-*`, `CVE-2023-2453*`).

**Rationale:** These are detections in Go binaries the upstream
maintainer shipped (typically `gosu`, build helpers, or — in the Ollama
case — the daemon binary itself). They are not on Meridian's
authored-code runtime path; the affected binaries either run once at
container init under a privileged context already controlled by the
orchestrator, or are part of the upstream maintainer's own runtime.
Same upstream-rebuild mechanism applies; same monthly digest-bump check.

**Affects:** pgvector/pgvector:pg17, postgres:17-alpine, redis:7-alpine,
langfuse images, ollama/ollama:0.22.0.

**Review date:** 2026-05-29.

### C. Application-level findings in pinned dependencies

**Scope:** Findings in application dependencies that are pinned at the
current upstream release. Examples: `CVE-2026-4926` (path-to-regexp inside
Langfuse worker), `CVE-2026-30836` (smallstep/certificates inside Caddy),
`CVE-2026-33186` (gRPC inside Caddy), `CVE-2026-34986` (go-jose inside
Caddy), `CVE-2026-32597` (PyJWT inside LiteLLM), `CVE-2025-67221` (orjson
inside LiteLLM), `CVE-2024-6345` and `CVE-2025-47273` (setuptools inside
LiteLLM image), `CVE-2026-33671` (picomatch shipped inside the LiteLLM
Node tooling tree).

**Rationale:** These are upstream-fixed in newer versions of the carrier
images, but the carrier images themselves have not yet republished. Same
posture: monthly digest-bump check (D25) catches these when upstream
re-releases. We do not patch upstream images locally because doing so
breaks the digest-pin guarantee. The LiteLLM-specific Python deps will
likely re-release on the next stable cut; the picomatch finding is in
Node tooling not on the proxy's runtime path.

**Affects:** caddy:2-alpine, langfuse/langfuse-worker:3.172.0,
ghcr.io/berriai/litellm:v1.83.10-stable.

**Review date:** 2026-05-29.

## Posture in production

The exception list above is appropriate for a local-first dev stack with
images pinned to digests. Production deployment context will narrow the
exceptions:

- Production base images will be hardened distributions (Chainguard, Bottlerocket,
  or equivalent) with current patches.
- Production CI will run `make scan` on every build with no exceptions for
  application-level findings; only OS-package transitive CVEs that lack a
  fix upstream will remain documented exceptions, and each one will carry a
  named owner.
- The monthly digest-bump check graduates from operator-driven to
  automated PRs gated by review.

This document and `.trivyignore` are reviewed at every phase audit and any
time `make scan` introduces new findings.
