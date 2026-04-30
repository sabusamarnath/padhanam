"""Parser test enforcing apps/api/Dockerfile workspace member coverage.

The structural promotion of an env-passthrough pattern that has bitten
across S9, S10, and S11. Each instance was a comment-level rule that
drifted because the source of truth (the workspace member list in the
root ``pyproject.toml``) was decoupled from the deployment surface
(the Dockerfile's ``COPY`` directives that put each member's
``pyproject.toml`` into the image at the path ``uv sync --frozen``
expects). Adding a new context to the workspace without remembering to
update the Dockerfile produced a build failure that surfaced only at
the next image rebuild — sometimes sessions later.

This test parses ``apps/api/Dockerfile`` and the root ``pyproject.toml``,
walks the declared workspace members, and asserts that each member has
a corresponding ``COPY`` directive placing its ``pyproject.toml`` into
the image at the expected path. The parse is line-oriented (Dockerfile
syntax is line-oriented) and matches the pattern from the S11 host-
port-binding test: parse-and-assert against a manifest, fail CI on
drift, no comment-level enforcement.

The S11 reflection's "checklist promotion candidate" framing names the
trigger: when a comment-level rule has bitten three times across the
package, the cost of a parser-level structural test is justified by
the recurrence. Three is the threshold; this test is the third
promotion in P3 (after S10's plaintext-in-state AST test and S11's
host-port-binding parser test).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "apps" / "api" / "Dockerfile"
ROOT_PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


_COPY_PYPROJECT_RE = re.compile(
    r"^\s*COPY\s+(\S+/pyproject\.toml)\s+\./(\S+/?)\s*$"
)


def _workspace_members() -> list[str]:
    """Return the workspace member list declared in the root pyproject."""
    with ROOT_PYPROJECT_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    members = (
        data.get("tool", {})
        .get("uv", {})
        .get("workspace", {})
        .get("members", [])
    )
    return list(members)


def _dockerfile_pyproject_copies() -> dict[str, str]:
    """Return source-path → destination-path pairs for every ``COPY ...
    pyproject.toml`` directive in apps/api/Dockerfile.

    Multi-line and continuation forms are out of scope; the existing
    Dockerfile uses one COPY per workspace member on its own line, and
    the test's invariant is that adding a new member requires a new
    one-line COPY.
    """
    copies: dict[str, str] = {}
    for raw_line in DOCKERFILE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0]
        match = _COPY_PYPROJECT_RE.match(line)
        if match is None:
            continue
        source_pyproject = match.group(1)
        dest = match.group(2).rstrip("/")
        copies[source_pyproject] = dest
    return copies


def _expected_copy_for(member: str) -> tuple[str, str]:
    """Source path and destination directory the Dockerfile must use
    for a workspace member named ``member``."""
    return (f"{member}/pyproject.toml", member)


def test_each_workspace_member_pyproject_is_copied_into_image() -> None:
    """For every workspace member declared in the root pyproject, the
    Dockerfile must COPY that member's pyproject.toml into the image
    at the expected path. The path is symmetric: a member at
    ``contexts/X`` has its pyproject COPYed to ``./contexts/X/``."""
    members = _workspace_members()
    assert members, "root pyproject declares no workspace members"

    copies = _dockerfile_pyproject_copies()

    missing: list[str] = []
    wrong_destination: dict[str, tuple[str, str]] = {}
    for member in members:
        expected_source, expected_dest = _expected_copy_for(member)
        if expected_source not in copies:
            missing.append(member)
            continue
        actual_dest = copies[expected_source]
        if actual_dest != expected_dest:
            wrong_destination[member] = (actual_dest, expected_dest)

    assert missing == [], (
        "Workspace member(s) missing COPY directive in "
        "apps/api/Dockerfile (each member's pyproject.toml must be "
        "COPYed into the image so `uv sync --frozen` resolves the "
        "workspace; see S9/S10/S11 reflections on recurrence): "
        + repr(missing)
    )
    assert wrong_destination == {}, (
        "Workspace member COPYed to unexpected destination in "
        "apps/api/Dockerfile (expected `./<member>/`): "
        + repr(wrong_destination)
    )


def test_dockerfile_does_not_copy_unknown_pyproject_files() -> None:
    """Every COPY ...pyproject.toml in the Dockerfile must correspond
    to a declared workspace member. Catches stale COPYs left behind
    after a member is removed from the workspace."""
    members = set(_workspace_members())
    copies = _dockerfile_pyproject_copies()

    stale: list[str] = []
    for source_pyproject in copies:
        member = source_pyproject.removesuffix("/pyproject.toml")
        if member not in members:
            stale.append(source_pyproject)

    assert stale == [], (
        "apps/api/Dockerfile COPYs a pyproject.toml that is not a "
        "current workspace member (stale entry left after rename or "
        "removal): " + repr(stale)
    )
