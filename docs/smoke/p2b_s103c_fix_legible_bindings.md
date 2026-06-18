# S103c-fix smoke — legible bindings (the why, match strength, workable unlink)

Surface-mostly over S103c. Recompute-on-read + front-end; no migration, no matcher
change, no D-entry.

## Verified this session (code + live read on the real corpus)

- **Suite green.** `tests/unit` passes; `tests/_enforcement` green; **import-linter
  48/0**. New: `binding_rationale` band tests (exact→strong, distinctive
  keyword→medium, incidental→weak, alias→weak, classifier→honest) + a bulk-unlink
  one-record-each test; served-HTML guards for the why, the strength badge, the
  triage filter, the in-place `subRefresh`, and the bulk path.
- **Diff is surface + read-side only (AC4).** `goal_assessment.py` additions only
  (the matcher inference unchanged, grep-confirmed), `read_element_evidence.py`,
  the DTO, the bindings endpoint, `daily_driver.html`. No migration, no
  `correlate_goal_facets` change, consume side untouched.
- **Live recompute on the real corpus.** `read_element_bindings` recomputes the why
  + the match-strength band for every binding (no storage change). On the personal
  tenant: **421 weak / 275 medium / 166 strong** — 49% weak, the triage target.
  Sample weak whys expose the trap: "Music practice Megan" → matched **"practice"**
  (an incidental token shared across elements).
- **The honest why (live find + fix).** The 166 "strong" bindings were *all* the
  D183 job-search-email classifier (tier `lexical_exact`, basis `email-job-search`)
  — the lexical matcher produced **zero** exact title==label matches on this corpus.
  They first showed `matched "Receive a job offer"`, implying a string match that
  never happened; fixed to render **"job-search classifier"** so the why never
  misleads (the strength stays strong — the rule is high-confidence).
- **The interactive lens is served (AC5).** The rebuilt image (`8a4078c`) serves
  the why + strength badge, the weak-only triage filter, the expanded-through-unlink
  behaviour, and the bulk "Unlink selected". 5/5 tenant-isolation contract guards
  still pass live.

## The honest framing (recorded)

What is shown is **lexical match strength, not correctness**. The matcher is
lexical+alias only: tier orders it, discriminativeness breaks keyword ties, and a
high-strength match on an incidental token is the trap the why exposes. Genuine
semantic confidence is an embedding-tier property, deferred. That all 166 strong
bindings are the classifier (not lexical exact) is itself the reflection-1 signal:
the lexical tier has no exact matches to lean on, so the embedding tier's value
rises as authoring saturates.

## Operator-gated

The reflection — did the why + strength let you triage, and did strength ever
mislead (a high-strength binding you still had to relink because the match was
incidental) — is the operator's browser pass. The tools are shipped, served, and
live-verified; `make build-api` advanced the pin to `8a4078c`.
