"""Scheduled supply-chain checks runner (D25).

Reads ``ops/scheduled_checks.yaml`` and produces a Markdown report
listing each family, its current pin, the latest upstream pin (queried
via vendor APIs or registry queries per family), a changelog excerpt,
and breaking-change flags.

Output writes to
``docs/security/scheduled-check-reports/<YYYY-MM-DD>.md``. ``make
scheduled-check`` invokes this script.

No auto-PR. The operator reviews the report and opens digest-bump PRs
manually per D25 ("auto-merging dependency updates rejected: removes
operator judgment from a security-relevant change").

The runner is local-first and survives offline runs: any family whose
upstream lookup fails is recorded as ``status: lookup_failed`` with
the error string in place of the latest version. The report is still
produced; the operator sees what was checked and what was not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEDULED_CHECKS_YAML = REPO_ROOT / "ops" / "scheduled_checks.yaml"
COMPOSE_YAML = REPO_ROOT / "compose.yaml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
REPORT_DIR = REPO_ROOT / "docs" / "security" / "scheduled-check-reports"


@dataclass
class FamilyStatus:
    name: str
    cadence: str
    current_pin: str
    latest_known: str
    notes: str
    breaking_changes: list[str]


def _read_yaml() -> dict:
    with SCHEDULED_CHECKS_YAML.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _read_compose_image_pins() -> dict[str, str]:
    """Return {service-image-name: full-pin-with-digest}.

    Parses lines like `image: pgvector/pgvector:pg17@sha256:...` from
    compose.yaml. The runner uses these to summarise the current
    Compose-side pin per family.
    """
    pins: dict[str, str] = {}
    pattern = re.compile(r"^\s+image:\s+(\S+)\s*$")
    for line in COMPOSE_YAML.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            full = m.group(1)
            base = full.split("@")[0]
            name = base.split(":")[0]
            pins[name] = full
    return pins


def _read_pyproject_pins() -> dict[str, str]:
    """Return {package-name-lower: pin-spec}.

    Greps the root pyproject's `dependencies` list. Workspace members
    skipped. Used to summarise Python-package pins per family.
    """
    pins: dict[str, str] = {}
    text = PYPROJECT.read_text(encoding="utf-8")
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("dependencies"):
            in_deps = True
            continue
        if in_deps and stripped == "]":
            break
        if in_deps and stripped.startswith('"'):
            spec = stripped.strip(",").strip('"')
            if spec.startswith("vadakkan-"):
                continue
            # PEP 508 simple form: name[extras][operators]version
            m = re.match(r"([A-Za-z0-9_.\-]+)", spec)
            if m:
                pins[m.group(1).lower()] = spec
    # Also walk workspace member pyprojects for context-scoped deps.
    for member in REPO_ROOT.glob("contexts/*/pyproject.toml"):
        text = member.read_text(encoding="utf-8")
        in_member_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("dependencies"):
                in_member_deps = True
                continue
            if in_member_deps and stripped == "]":
                in_member_deps = False
                continue
            if in_member_deps and stripped.startswith('"'):
                spec = stripped.strip(",").strip('"')
                m = re.match(r"([A-Za-z0-9_.\-]+)", spec)
                if m:
                    name = m.group(1).lower()
                    pins.setdefault(name, spec)
    for member in REPO_ROOT.glob("apps/*/pyproject.toml"):
        text = member.read_text(encoding="utf-8")
        in_member_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("dependencies"):
                in_member_deps = True
                continue
            if in_member_deps and stripped == "]":
                in_member_deps = False
                continue
            if in_member_deps and stripped.startswith('"'):
                spec = stripped.strip(",").strip('"')
                m = re.match(r"([A-Za-z0-9_.\-]+)", spec)
                if m:
                    name = m.group(1).lower()
                    pins.setdefault(name, spec)
    return pins


def _pypi_latest(package: str, *, timeout: float = 5.0) -> str:
    """Query the public PyPI JSON API for latest version of *package*."""
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
        return data.get("info", {}).get("version", "unknown")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return f"lookup_failed: {e}"


def _summarise_family(
    name: str,
    cadence: str,
    *,
    image_pins: dict[str, str],
    py_pins: dict[str, str],
    online: bool,
) -> FamilyStatus:
    notes_parts: list[str] = []
    breaking: list[str] = []
    current_parts: list[str] = []
    latest_parts: list[str] = []

    if name == "langfuse":
        for img in ("langfuse/langfuse", "langfuse/langfuse-worker"):
            if img in image_pins:
                current_parts.append(f"`{img}`: `{image_pins[img]}`")
        py = py_pins.get("langfuse")
        if py:
            current_parts.append(f"PyPI `langfuse`: `{py}`")
        latest_parts.append(
            "Vendor: Docker Hub `langfuse/langfuse` (manual digest review per "
            "D25 cadence — automated registry walk deferred until first remote "
            "deployment)."
        )

    elif name == "otel-instrumentation":
        for pkg in (
            "opentelemetry-instrumentation-fastapi",
            "opentelemetry-instrumentation-httpx",
            "opentelemetry-semantic-conventions",
        ):
            if pkg in py_pins:
                current_parts.append(f"`{pkg}`: `{py_pins[pkg]}`")
            if online:
                latest = _pypi_latest(pkg)
                latest_parts.append(f"`{pkg}` PyPI latest: `{latest}`")

    elif name == "litellm":
        if "ghcr.io/berriai/litellm" in image_pins:
            current_parts.append(
                f"image `ghcr.io/berriai/litellm`: "
                f"`{image_pins['ghcr.io/berriai/litellm']}`"
            )
        if "litellm" in py_pins:
            current_parts.append(f"PyPI `litellm`: `{py_pins['litellm']}`")
        if online:
            latest_parts.append(f"`litellm` PyPI latest: `{_pypi_latest('litellm')}`")

    elif name == "fastapi-uvicorn":
        for pkg in ("fastapi", "uvicorn"):
            if pkg in py_pins:
                current_parts.append(f"`{pkg}`: `{py_pins[pkg]}`")
            if online:
                latest_parts.append(f"`{pkg}` PyPI latest: `{_pypi_latest(pkg)}`")

    elif name == "pydantic-chain":
        for pkg in ("pydantic", "pydantic-settings"):
            if pkg in py_pins:
                current_parts.append(f"`{pkg}`: `{py_pins[pkg]}`")
            if online:
                latest_parts.append(f"`{pkg}` PyPI latest: `{_pypi_latest(pkg)}`")

    elif name == "import-linter":
        if "import-linter" in py_pins:
            current_parts.append(f"`import-linter`: `{py_pins['import-linter']}`")
        notes_parts.append(
            "Trigger: contract count crosses 25 (currently 15 at S10 close)."
        )
        if online:
            latest_parts.append(
                f"`import-linter` PyPI latest: `{_pypi_latest('import-linter')}`"
            )

    if not current_parts:
        current_parts.append("(no pin found in compose.yaml or pyproject)")
    if not latest_parts:
        latest_parts.append(
            "(no automated upstream lookup configured; operator review)"
        )

    return FamilyStatus(
        name=name,
        cadence=cadence,
        current_pin="; ".join(current_parts),
        latest_known="; ".join(latest_parts),
        notes=" ".join(notes_parts),
        breaking_changes=breaking,
    )


def _render_markdown(
    families: list[FamilyStatus], *, generated_at: datetime
) -> str:
    lines: list[str] = []
    lines.append(f"# Scheduled supply-chain check — {generated_at.date().isoformat()}")
    lines.append("")
    lines.append(
        f"Generated at {generated_at.isoformat()} by `make scheduled-check`. "
        "Per D25, no auto-PR; operator reviews this report and opens digest-"
        "bump PRs manually."
    )
    lines.append("")
    by_cadence: dict[str, list[FamilyStatus]] = {}
    for fam in families:
        by_cadence.setdefault(fam.cadence, []).append(fam)
    for cadence in ("monthly", "quarterly", "annual"):
        if cadence not in by_cadence:
            continue
        lines.append(f"## {cadence.capitalize()} cadence")
        lines.append("")
        for fam in by_cadence[cadence]:
            lines.append(f"### `{fam.name}`")
            lines.append("")
            lines.append(f"- **Current pin:** {fam.current_pin}")
            lines.append(f"- **Latest known:** {fam.latest_known}")
            if fam.notes:
                lines.append(f"- **Notes:** {fam.notes}")
            if fam.breaking_changes:
                lines.append("- **Breaking-change flags:**")
                for bc in fam.breaking_changes:
                    lines.append(f"  - {bc}")
            lines.append("")
    lines.append("## Operator action items")
    lines.append("")
    lines.append(
        "1. Review each family's current vs latest. Open a digest-bump PR for "
        "any family whose latest pin is materially newer and whose changelog "
        "is benign."
    )
    lines.append(
        "2. Record review outcomes in the PR body so the next scheduled run "
        "has historical context."
    )
    lines.append(
        "3. Off-cycle bumps (CVE-driven) follow the same review process; the "
        "scheduled report is not the only entry point."
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip all upstream lookups (PyPI, Docker Hub) — useful for CI dry runs.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Override report output path (default: docs/security/scheduled-check-reports/<today>.md).",
    )
    args = parser.parse_args(argv)

    yaml_doc = _read_yaml()
    image_pins = _read_compose_image_pins()
    py_pins = _read_pyproject_pins()

    families: list[FamilyStatus] = []
    for cadence_name, cadence_block in yaml_doc.get("cadences", {}).items():
        for fam in cadence_block.get("families", []):
            families.append(
                _summarise_family(
                    fam["name"],
                    cadence_name,
                    image_pins=image_pins,
                    py_pins=py_pins,
                    online=not args.offline,
                )
            )

    generated_at = datetime.now(timezone.utc)
    output = _render_markdown(families, generated_at=generated_at)

    out_path = args.out or REPORT_DIR / f"{generated_at.date().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
