#!/usr/bin/env python3
"""Scrub guard — block real names from re-entering committed files (S103ai).

Fails if any real name from the git-ignored ``charter/.scrub-mapping`` (the real-name
column, left of ``=>``) appears in any git-tracked file. This is the *enforced* form of
the charter principle "Real names never enter committed files; placeholders go in at
write time": known-name re-leakage becomes impossible, catching the failure class that
leaked a job search into public history (real company/contact/goal names in session logs
and — worse — in test fixtures seeded from live data).

Scope + honest residual: this catches names already in the mapping. A brand-new real name
not yet mapped still relies on writer judgment at write time (the residual recorded in
principles.md). Add new names to the mapping as they arise so the guard covers them.

The mapping is a secret, absent from fresh clones. When it is absent this check no-ops, so
it never blocks a contributor who does not hold the mapping.

Run: ``python3 scripts/check_scrub.py`` (or ``make scrub-check``). Wire as a pre-commit
hook via ``make install-hooks`` (sets ``core.hooksPath=.githooks``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MAPPING = Path("charter/.scrub-mapping")


def real_names() -> list[str]:
    """The blanket-checkable real names from the mapping. Names in a *context-only*
    section (a comment header containing "context" / "not for global replace" — e.g.
    Motion, Reclaim, which were scrubbed only in their product occurrences and legitimately
    appear as ordinary words) are excluded from the blanket check, else the guard would
    flag every ordinary use."""
    if not MAPPING.exists():
        return []
    names: list[str] = []
    context_only = False
    for raw in MAPPING.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            low = line.lower()
            context_only = "context" in low or "not for global" in low
            continue
        if "=>" not in line:
            continue
        if context_only:
            continue
        name = line.split("=>", 1)[0].strip()
        if name:
            names.append(name)
    return names


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [f for f in result.stdout.splitlines() if f]


def main() -> int:
    names = real_names()
    if not names:
        print("scrub-check: no charter/.scrub-mapping present — skipping (nothing to enforce)")
        return 0
    pattern = re.compile(
        r"(?<![A-Za-z0-9])("
        + "|".join(re.escape(n) for n in sorted(set(names), key=len, reverse=True))
        + r")(?![A-Za-z0-9])"
    )
    files = tracked_files()
    violations: list[tuple[str, list[str]]] = []
    for path in files:
        if path == str(MAPPING):
            continue
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hits = sorted({m.group(1) for m in pattern.finditer(text)})
        if hits:
            violations.append((path, hits))
    if violations:
        print(
            "scrub-check: FAIL — real names from charter/.scrub-mapping found in tracked files:",
            file=sys.stderr,
        )
        for path, hits in violations:
            print(f"  {path}: {', '.join(hits)}", file=sys.stderr)
        print(
            "\nReplace each with its stable placeholder (see charter/.scrub-mapping) "
            "before committing.",
            file=sys.stderr,
        )
        return 1
    print(f"scrub-check: OK — {len(names)} mapped names, 0 present across {len(files)} tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
