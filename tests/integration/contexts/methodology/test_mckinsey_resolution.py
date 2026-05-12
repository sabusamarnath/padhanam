"""End-to-end resolution test for McKinsey 7-Step methodology (S26b).

Asserts the migration at ``0008_create_mckinsey_7_step`` lands the
methodology and its seven role aggregates correctly:

1. McKinsey 7-Step exists on control-plane Postgres at the name the
   migration writes.
2. The methodology revision carries seven role_refs in the brief's
   sequential order (ProblemFramer ... Communicator).
3. Each role_ref's overrides exposes the D87 structured shape with
   ``mode = "augment"`` and value verbatim from the brief.
4. Each role's revision-1 hash equals the hash the use-case path
   would compute (golden-hash assertion via the application-layer
   helper).
5. The methodology's revision-1 hash equals the hash the use-case
   path would compute over the canonical content payload.
6. The MethodologyLookupAdapter from apps/cli/_cross_context.py
   resolves the first role_ref correctly through the role-aware
   resolution path.

This is the golden-hash assertion the brief specifies at S26b
commit 4 AC #13, #14, #15. The migration's inlined helpers must
produce byte-equivalent canonical JSON to the application-layer
helpers; this test pins the invariant.

The test reads the McKinsey methodology by name rather than by a
fixed UUID because the migration uses ``uuid4()`` for the eight
inserted rows (down-and-up cycles produce different UUIDs each
time). The role's content hash is independent of role_id and
remains stable across cycles; the methodology hash depends on the
resolved role_ids and is content-determined given the persisted
role_ids the test reads back.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID

import pytest

from apps.cli._cross_context import MethodologyLookupAdapter
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    RolePostgresRepository,
)
from contexts.methodology.application import (
    get_methodology_template,
    get_role_template,
    list_methodology_templates,
)
from contexts.methodology.application.use_cases import (
    _content_payload as _methodology_content_payload,
    _role_content_payload,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger
from padhanam.security import OPERATOR_ROLE, Principal
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)
from shared_kernel import TenantId


_EXPECTED_ROLE_NAMES_IN_BRIEF_ORDER: tuple[str, ...] = (
    "ProblemFramer",
    "Disaggregator",
    "Prioritiser",
    "Planner",
    "Analyst",
    "Synthesiser",
    "Communicator",
)


# Per-role overrides from the brief verbatim. Each value is the
# system_prompt addition the migration persists at mode "augment".
_EXPECTED_OVERRIDES: dict[str, str] = {
    "ProblemFramer": (
        "Apply the SCQ framework (Situation, Complication, Question) when "
        "framing"
    ),
    "Disaggregator": (
        "Apply MECE (Mutually Exclusive, Collectively Exhaustive) "
        "decomposition; produce an issue tree"
    ),
    "Prioritiser": (
        "Use impact-tractability matrix; flag the top quartile as priorities"
    ),
    "Planner": (
        "Workplan structure: hypothesis, analyses, data needed, owner, "
        "deadline, deliverable"
    ),
    "Analyst": (
        "Findings include data, source citations, confidence level"
    ),
    "Synthesiser": (
        "Apply pyramid principle to storyline construction"
    ),
    "Communicator": (
        "Default communication style is structured prose with executive "
        "summary"
    ),
}


# Substrate-mapped constraint-bundle defaults from S26b's pre-write
# reconciliation. Shared across all seven roles; mirrored from the
# migration so the test can recompute the canonical role payload and
# compare against the persisted hash.
_EXPECTED_BUNDLE = {
    "source_ids": (),
    "tool_allowlist": (),
    "retrieval_strategy": {"strategy": "parallel_rrf", "params": {}},
    "filter_tree": {"node": {}},
    "top_k": 8,
    "min_score": Decimal("0.5"),
    "model_selection": "qwen2.5:7b",
}


def _operator() -> Principal:
    return Principal(
        subject="test-operator",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="test-token-op",
    )


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def repos(
    event_loop: asyncio.AbstractEventLoop,
) -> Iterator[tuple[MethodologyPostgresRepository, RolePostgresRepository]]:
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = file_security_event_logger()
    methodology_repo = MethodologyPostgresRepository.from_settings(
        settings=settings, security_events=sec
    )
    role_repo = RolePostgresRepository.from_settings(
        settings=settings, security_events=sec
    )

    # Probe reachability without truncating tables — the migration
    # owns the McKinsey rows and the test asserts against them.
    async def probe() -> None:
        await methodology_repo.list_templates()

    try:
        event_loop.run_until_complete(probe())
    except Exception as e:
        event_loop.run_until_complete(methodology_repo.dispose())
        event_loop.run_until_complete(role_repo.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    try:
        yield methodology_repo, role_repo
    finally:
        event_loop.run_until_complete(methodology_repo.dispose())
        event_loop.run_until_complete(role_repo.dispose())


def _find_methodology_by_name(
    event_loop, methodology_repo, name: str
) -> UUID:
    templates = event_loop.run_until_complete(
        list_methodology_templates(
            principal=_operator(),
            repository=methodology_repo,
        )
    )
    match = next((t for t in templates if t.name == name), None)
    if match is None:
        pytest.skip(
            f"{name!r} not present on control-plane; run "
            f"`alembic --name control_plane upgrade head` first."
        )
    return match.id


def test_mckinsey_methodology_present_with_seven_role_refs_in_brief_order(
    event_loop, repos
) -> None:
    methodology_repo, role_repo = repos

    template_id = _find_methodology_by_name(
        event_loop, methodology_repo, "McKinsey 7-Step"
    )
    template, revision = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator(),
            repository=methodology_repo,
            template_id=template_id,
        )
    )

    assert template.name == "McKinsey 7-Step"
    assert revision.version == 1
    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert len(revision.role_refs) == 7

    # The role_refs preserve the brief's sequential order in storage
    # (the canonical hash payload sorts by role_id; storage order is
    # the brief's authoring order per AC #11).
    resolved_names: list[str] = []
    for ref in revision.role_refs:
        role_template, _ = event_loop.run_until_complete(
            get_role_template(
                principal=_operator(),
                repository=role_repo,
                template_id=ref.role_id,
                version=ref.role_version,
            )
        )
        resolved_names.append(role_template.name)
    assert tuple(resolved_names) == _EXPECTED_ROLE_NAMES_IN_BRIEF_ORDER


def test_each_role_ref_carries_structured_augment_override_verbatim(
    event_loop, repos
) -> None:
    methodology_repo, role_repo = repos
    template_id = _find_methodology_by_name(
        event_loop, methodology_repo, "McKinsey 7-Step"
    )
    _, revision = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator(),
            repository=methodology_repo,
            template_id=template_id,
        )
    )

    for role_name, ref in zip(
        _EXPECTED_ROLE_NAMES_IN_BRIEF_ORDER, revision.role_refs, strict=True
    ):
        # D87 structured shape: each entry's value is {mode, value}
        # keyed by role-bundle field. The brief specifies only
        # system_prompt overrides; no other keys.
        assert set(ref.overrides.keys()) == {"system_prompt"}, (
            f"{role_name} carries unexpected override keys: "
            f"{sorted(ref.overrides.keys())!r}"
        )
        sp = ref.overrides["system_prompt"]
        assert sp == {
            "mode": "augment",
            "value": _EXPECTED_OVERRIDES[role_name],
        }, (
            f"{role_name} override mismatches brief: persisted={sp!r}"
        )


def test_each_role_revision_hash_matches_use_case_path(
    event_loop, repos
) -> None:
    """Golden-hash assertion per AC #13: each role's persisted hash
    equals what compute_revision_hash would produce against the role's
    content payload via the application-layer helper.
    """
    methodology_repo, role_repo = repos
    template_id = _find_methodology_by_name(
        event_loop, methodology_repo, "McKinsey 7-Step"
    )
    _, methodology_rev = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator(),
            repository=methodology_repo,
            template_id=template_id,
        )
    )

    for ref in methodology_rev.role_refs:
        role_template, role_rev = event_loop.run_until_complete(
            get_role_template(
                principal=_operator(),
                repository=role_repo,
                template_id=ref.role_id,
                version=ref.role_version,
            )
        )
        assert role_rev.version == 1
        assert role_rev.previous_revision_hash == GENESIS_REVISION_HASH

        # Recompute via the application-layer helper from the
        # persisted role's content. Byte-equivalent to the migration's
        # inlined helper if the canonical JSON serialisation is stable.
        expected_payload = _role_content_payload(
            name=role_template.name,
            description=role_template.description,
            system_prompt=role_rev.system_prompt,
            source_ids=role_rev.source_ids,
            tool_allowlist=role_rev.tool_allowlist,
            retrieval_strategy=role_rev.retrieval_strategy,
            filter_tree=role_rev.filter_tree,
            top_k=role_rev.top_k,
            min_score=role_rev.min_score,
            model_selection=role_rev.model_selection,
        )
        expected_hash = compute_revision_hash(
            content_payload=expected_payload,
            previous_hash=GENESIS_REVISION_HASH,
        )
        assert role_rev.this_revision_hash == expected_hash, (
            f"{role_template.name} hash mismatch: persisted="
            f"{role_rev.this_revision_hash!r} expected={expected_hash!r}"
        )

        # Substrate-mapped constraint bundle matches the brief.
        assert role_rev.source_ids == _EXPECTED_BUNDLE["source_ids"]
        assert role_rev.tool_allowlist == _EXPECTED_BUNDLE["tool_allowlist"]
        assert role_rev.retrieval_strategy == _EXPECTED_BUNDLE["retrieval_strategy"]
        assert role_rev.filter_tree == _EXPECTED_BUNDLE["filter_tree"]
        assert role_rev.top_k == _EXPECTED_BUNDLE["top_k"]
        assert role_rev.min_score == _EXPECTED_BUNDLE["min_score"]
        assert role_rev.model_selection == _EXPECTED_BUNDLE["model_selection"]


def test_methodology_revision_hash_matches_use_case_path(
    event_loop, repos
) -> None:
    """Golden-hash assertion per AC #14: the methodology's persisted
    hash equals what compute_revision_hash would produce over
    (name, description, role_refs sorted by role_id, overrides
    canonically serialised).
    """
    methodology_repo, role_repo = repos
    template_id = _find_methodology_by_name(
        event_loop, methodology_repo, "McKinsey 7-Step"
    )
    template, revision = event_loop.run_until_complete(
        get_methodology_template(
            principal=_operator(),
            repository=methodology_repo,
            template_id=template_id,
        )
    )

    expected_payload = _methodology_content_payload(
        name=template.name,
        description=template.description,
        role_refs=revision.role_refs,
    )
    expected_hash = compute_revision_hash(
        content_payload=expected_payload,
        previous_hash=GENESIS_REVISION_HASH,
    )
    assert revision.this_revision_hash == expected_hash, (
        f"McKinsey methodology revision-1 hash mismatch: "
        f"persisted={revision.this_revision_hash!r} expected={expected_hash!r}"
    )


def test_methodology_lookup_adapter_resolves_first_role(
    event_loop, repos
) -> None:
    """Exercises the role-aware MethodologyLookupAdapter against the
    McKinsey methodology. Phase 1 adapter contract returns the first
    role_ref's resolved bundle (the seven-role-resolution surface
    defers to a Phase 2 adapter extension; this test pins the first-
    role behaviour against the live stack).
    """
    methodology_repo, role_repo = repos
    template_id = _find_methodology_by_name(
        event_loop, methodology_repo, "McKinsey 7-Step"
    )

    adapter = MethodologyLookupAdapter(
        methodology_repository=methodology_repo,
        role_repository=role_repo,
    )
    view = event_loop.run_until_complete(
        adapter(
            template_id=template_id,
            version=None,
            principal=_operator(),
        )
    )

    # The first role_ref in storage order is ProblemFramer per the
    # brief. The adapter resolves its content bundle and surfaces the
    # role identity through MethodologyView.role_id / role_version.
    assert view.methodology_template_id == template_id
    assert view.methodology_version == 1
    assert view.role_version == 1

    # Resolve the role separately to confirm the adapter returned
    # ProblemFramer's content.
    role_template, role_rev = event_loop.run_until_complete(
        get_role_template(
            principal=_operator(),
            repository=role_repo,
            template_id=view.role_id,
            version=view.role_version,
        )
    )
    assert role_template.name == "ProblemFramer"
    assert view.system_prompt == role_rev.system_prompt
    assert view.tool_allowlist == role_rev.tool_allowlist
    assert view.retrieval_strategy == role_rev.retrieval_strategy
