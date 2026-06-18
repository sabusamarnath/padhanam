"""Report the size of the charter and log files; flag living-state files over bound.

The mechanical form of the charter-and-log retention rule
(``charter/methodology.md``, "Charter and log retention (living-state versus
ledger)"). Living-state files hold current truth and are bounded by contract;
append-only ledgers hold history and are windowed into a hot file plus cold
archives under ``docs/archive/``. This check reports every charter/log file's
size and flags any *living-state* file over its bound, so the read-at-start
ritual (principles, decisions index, the active package note, current-package,
the latest sessions) keeps fitting one context window.

Run at every package close::

    python -m ops.charter_size_check            # report
    python -m ops.charter_size_check --check    # exit non-zero if any bound tripped

Dependency-free (stdlib only); local-first (reads files, no stack required).
Token sizes are approximate (``chars // 4``), enough to spot a balloon — not a
billing-grade count. Bounds are deliberately generous: they catch the 72k
current-package / 312k sessions regression this rule was written to prevent,
not normal growth. Tune the BOUNDS table when a package legitimately trips one.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Files reported every run (charter current-truth + the two logs that ballooned).
REPORTED = [
    "charter/principles.md",
    "charter/decisions.md",
    "charter/roadmap.md",
    "charter/schema.md",
    "charter/methodology.md",
    "charter/deferred-decisions.md",
    "charter/packages.md",
    "charter/current-package.md",
    "log/sessions.md",
    "log/captures.md",
    "log/packages.md",
]

# Living-state files bounded by contract, in approximate tokens. Over-bound is
# a flag to window (sessions) or to check for accumulated cruft (current-package).
# Ledgers (decisions.md) are NOT bounded here: they stay whole behind the index
# until the two-threshold trigger; see the retention rule.
BOUNDS = {
    "charter/current-package.md": 20_000,   # the one-open-package contract
    "log/sessions.md": 60_000,              # the open package's sessions window
}

# Soft note surfaced (not flagged) so the next pressure point is visible.
NOTES = {
    "charter/decisions.md": (
        "ledger, whole behind its top-of-file index; body split by era waits for "
        "the two-threshold trigger (index-only read blocks AND a second size bound)"
    ),
}


def approx_tokens(text: str) -> int:
    return len(text) // 4


def fmt(n: int) -> str:
    return f"{n:,}"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    over: list[str] = []

    print("Charter and log size check (retention rule; bounds in approx tokens)")
    print("-" * 78)
    print(f"{'file':40} {'bytes':>11} {'~tokens':>9}  status")
    print("-" * 78)

    for rel in REPORTED:
        p = REPO / rel
        if not p.exists():
            print(f"{rel:40} {'MISSING':>11} {'':>9}  (not found)")
            continue
        raw = p.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        toks = approx_tokens(text)
        bound = BOUNDS.get(rel)
        if bound is None:
            status = NOTES.get(rel, "reference / ledger")
        elif toks > bound:
            status = f"OVER BOUND ({fmt(bound)}) — window at package close"
            over.append(rel)
        else:
            status = f"ok (bound {fmt(bound)})"
        print(f"{rel:40} {fmt(len(raw)):>11} {fmt(toks):>9}  {status}")

    print("-" * 78)
    if over:
        print(f"FLAGGED {len(over)} living-state file(s) over bound: {', '.join(over)}")
        print("Per the retention rule, window the flagged file(s) into docs/archive/ "
              "before the next session inherits the cost.")
    else:
        print("All living-state files within bound.")

    if check and over:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
