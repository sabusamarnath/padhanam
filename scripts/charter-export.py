#!/usr/bin/env python3
"""Charter snapshot export — session-close tooling.

Builds the flattened charter snapshot the operator uploads to the Claude.ai
project mirror so strategic-mode conversations have the charter as searchable
project knowledge.

The file set is an *allowlist*, governed entirely by
``docs/charter-archive-manifest.md``. This script reads that manifest as its
single source of truth; it never globs the charter surface. New charter files,
briefs, and archives reach the snapshot only by being added to the manifest's
"## Keep" section deliberately — see the manifest for the rationale.

Output (both git-ignored — see .gitignore's ``charter-2026*/`` and ``/*.zip``):

    charter-YYYYMMDD-HHMM/       flattened snapshot directory
    charter-YYYYMMDD-HHMM.zip    the matching archive

Usage:
    make charter-export
    uv run python scripts/charter-export.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "docs" / "charter-archive-manifest.md"
KEEP_HEADING = "## Keep — the allowlist"

# Source directories whose direct children flatten to a bare filename.
# A file anywhere else is prefixed with its immediate parent directory name
# (see flat_name). This matches the convention documented in the manifest.
BARE_PARENTS = {"charter", "log"}

_ALLOWLIST_BULLET = re.compile(r"^-\s+`([^`]+)`")


def parse_allowlist(manifest: Path) -> list[str]:
    """Return the source paths listed under the manifest's "## Keep" section.

    Reads every bullet of the form ``- `<path>` `` between the Keep heading and
    the next ``## `` heading. Scoping to that section means backtick-quoted
    paths embedded in the Discard-section prose never leak into the snapshot.
    """
    in_keep = False
    paths: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_keep = line.strip() == KEEP_HEADING
            continue
        if in_keep:
            match = _ALLOWLIST_BULLET.match(line)
            if match:
                paths.append(match.group(1))
    return paths


def flat_name(rel_path: str) -> str:
    """Flatten a repo-relative source path to its snapshot filename.

    Files directly under ``charter/`` or ``log/``, and files at the repo root,
    keep their bare filename. Files anywhere else are prefixed with their
    immediate parent directory name::

        charter/bet.md                 -> bet.md
        log/sessions.md                -> sessions.md
        CLAUDE.md                      -> CLAUDE.md
        charter/packages/p13-epic.md   -> packages-p13-epic.md
        briefs/p13/framing.md          -> p13-framing.md
        charter/compliance/README.md   -> compliance-README.md
        charter/brand/tokens.css       -> brand-tokens.css
    """
    path = Path(rel_path)
    if len(path.parts) == 1:
        return path.name
    parent = path.parts[-2]
    if parent in BARE_PARENTS:
        return path.name
    return f"{parent}-{path.name}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the source -> snapshot mapping and write nothing.",
    )
    args = parser.parse_args()

    manifest_rel = MANIFEST.relative_to(REPO_ROOT)
    if not MANIFEST.is_file():
        print(f"error: manifest not found at {manifest_rel}", file=sys.stderr)
        return 1

    rel_paths = parse_allowlist(MANIFEST)
    if not rel_paths:
        print(
            f"error: empty allowlist — check the '{KEEP_HEADING}' section "
            f"of {manifest_rel}",
            file=sys.stderr,
        )
        return 1

    # Resolve every allowlisted path, checking existence and flat-name
    # collisions before writing anything.
    resolved: list[tuple[str, Path, str]] = []  # (rel_path, abs_path, flat_name)
    missing: list[str] = []
    flat_owner: dict[str, str] = {}
    collisions: list[str] = []
    for rel in rel_paths:
        src = REPO_ROOT / rel
        if not src.is_file():
            missing.append(rel)
            continue
        flat = flat_name(rel)
        if flat in flat_owner:
            collisions.append(f"  {flat}  <-  {flat_owner[flat]}  and  {rel}")
        else:
            flat_owner[flat] = rel
        resolved.append((rel, src, flat))

    if missing:
        print(
            f"error: {len(missing)} allowlisted file(s) not found "
            f"(fix the path in {manifest_rel}):",
            file=sys.stderr,
        )
        for rel in missing:
            print(f"  {rel}", file=sys.stderr)
        return 1
    if collisions:
        print("error: flat-name collisions in the allowlist:", file=sys.stderr)
        print("\n".join(collisions), file=sys.stderr)
        return 1

    by_flat = sorted(resolved, key=lambda row: row[2])
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    snapshot_dir = REPO_ROOT / f"charter-{stamp}"
    zip_path = REPO_ROOT / f"charter-{stamp}.zip"

    if args.dry_run:
        print(f"charter-export dry run — {len(resolved)} files from {manifest_rel}")
        for rel, _, flat in by_flat:
            print(f"  {rel}  ->  {flat}")
        print(f"would write: charter-{stamp}/  and  charter-{stamp}.zip")
        return 0

    # Regenerate the snapshot directory from scratch so a same-minute re-run
    # never leaves stale files behind.
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir()
    for _, src, flat in by_flat:
        shutil.copyfile(src, snapshot_dir / flat)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for _, src, flat in by_flat:
            archive.write(src, arcname=flat)

    print(f"charter-export — {len(resolved)} files (allowlist: {manifest_rel})")
    print(f"  dir: charter-{stamp}/")
    print(f"  zip: charter-{stamp}.zip")
    print("Upload the zip to the Claude.ai project mirror to refresh it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
