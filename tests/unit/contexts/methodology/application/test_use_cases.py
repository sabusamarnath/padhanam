"""Unit tests for methodology use cases (D74, refactored S26a-1 per D86).

Uses an in-memory fake repository to exercise the use case layer's
policy boundary, hash chain wiring, and revision-creation invariants
without touching Postgres. The integration tests at
``tests/integration/contexts/methodology/adapters/outbound/postgres/``
verify the adapter against the live control-plane DB.

Post-D86 the methodology revision carries ``role_refs`` rather than
the constraint bundle; the use case test mirror updates accordingly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.methodology.application import (
    RoleRef,
    create_methodology_template,
    get_methodology_template,
    list_methodology_templates,
    retire_methodology_template,
    update_methodology_template,
)
from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import (
    OPERATOR_ROLE,
    AuthorizationError,
    Principal,
)
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from shared_kernel import TenantId


def _operator_principal() -> Principal:
    return Principal(
        subject="system:control_plane",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op",
    )


def _tenant_principal() -> Principal:
    return Principal(
        subject="alice",
        tenant_id=TenantId("00000000-0000-4000-8000-00000000a001"),
        roles=frozenset({"audit.read"}),
        credential_ref="dev-token-a",
    )


_DEFAULT_ROLE_ID = UUID("00000000-0000-4000-8000-0000000c0001")


def _role_ref(role_id: UUID = _DEFAULT_ROLE_ID, role_version: int = 1) -> RoleRef:
    return RoleRef(role_id=role_id, role_version=role_version)


class _FakeMethodologyRepository:
    def __init__(self) -> None:
        self.templates: dict[UUID, MethodologyTemplate] = {}
        self.revisions: dict[UUID, list[MethodologyRevision]] = {}

    async def create_template(
        self,
        template: MethodologyTemplate,
        initial_revision: MethodologyRevision,
    ) -> MethodologyTemplate:
        self.templates[template.id] = template
        self.revisions[template.id] = [initial_revision]
        return template

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[MethodologyTemplate, MethodologyRevision]:
        if template_id not in self.templates:
            raise LookupError(f"methodology template {template_id} not found")
        revs = self.revisions[template_id]
        if version is None:
            return self.templates[template_id], revs[-1]
        for rev in revs:
            if rev.version == version:
                return self.templates[template_id], rev
        raise LookupError(
            f"revision for template {template_id} version {version} not found"
        )

    async def list_templates(self) -> list[MethodologyTemplate]:
        return [t for t in self.templates.values() if t.archived_at is None]

    async def add_revision(
        self,
        template_id: UUID,
        revision: MethodologyRevision,
    ) -> MethodologyRevision:
        self.revisions[template_id].append(revision)
        return revision

    async def archive_template(
        self,
        template_id: UUID,
    ) -> MethodologyTemplate:
        template = self.templates[template_id]
        archived = MethodologyTemplate(
            id=template.id,
            name=template.name,
            description=template.description,
            created_by_user_id=template.created_by_user_id,
            created_at=template.created_at,
            archived_at=datetime.now(timezone.utc),
        )
        self.templates[template_id] = archived
        return archived


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


def _create_kwargs(**overrides) -> dict:
    defaults = {
        "name": "TestMethodology",
        "description": "Test fixture",
        "role_refs": (_role_ref(),),
        "actor_user_id": "alice",
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def test_create_methodology_template_operator_succeeds(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, revision = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    assert template.name == "TestMethodology"
    assert revision.version == 1
    assert revision.previous_revision_hash == GENESIS_REVISION_HASH
    assert len(revision.this_revision_hash) == 64
    assert len(revision.role_refs) == 1


def test_create_methodology_template_tenant_rejected(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            create_methodology_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                **_create_kwargs(),
            )
        )
    assert repo.templates == {}
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "methodology.create_template"
        for e in sec.events
    )


def test_update_methodology_template_chains_hash_to_predecessor(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, rev1 = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    second_role = UUID("00000000-0000-4000-8000-0000000c0002")
    rev2 = event_loop.run_until_complete(
        update_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=template.id,
            role_refs=(_role_ref(role_id=second_role),),
            actor_user_id="alice",
        )
    )
    assert rev2.version == 2
    assert rev2.previous_revision_hash == rev1.this_revision_hash
    assert rev2.this_revision_hash != rev1.this_revision_hash


def test_update_methodology_template_tenant_rejected(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            update_methodology_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
                role_refs=(_role_ref(),),
                actor_user_id="alice",
            )
        )
    assert len(repo.revisions[template.id]) == 1
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "methodology.update_template"
        for e in sec.events
    )


def test_get_methodology_template_accepts_tenant_context(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    fetched_template, fetched_rev = event_loop.run_until_complete(
        get_methodology_template(
            principal=_tenant_principal(),
            repository=repo,
            template_id=template.id,
        )
    )
    assert fetched_template.id == template.id
    assert fetched_rev.version == 1
    assert len(fetched_rev.role_refs) == 1


def test_list_methodology_templates_excludes_archived(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    keep, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(name="KeepMethodology"),
        )
    )
    drop, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(name="DropMethodology"),
        )
    )
    event_loop.run_until_complete(
        retire_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            template_id=drop.id,
        )
    )
    listed = event_loop.run_until_complete(
        list_methodology_templates(
            principal=_tenant_principal(),
            repository=repo,
        )
    )
    assert {t.id for t in listed} == {keep.id}


def test_retire_methodology_tenant_rejected(event_loop) -> None:
    repo = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    template, _ = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo,
            security_events=sec,
            **_create_kwargs(),
        )
    )
    with pytest.raises(AuthorizationError):
        event_loop.run_until_complete(
            retire_methodology_template(
                principal=_tenant_principal(),
                repository=repo,
                security_events=sec,
                template_id=template.id,
            )
        )
    assert repo.templates[template.id].archived_at is None
    assert any(
        e.category is SecurityEventCategory.AUTHZ_DENIAL
        and e.action == "methodology.retire_template"
        for e in sec.events
    )


def test_hash_chain_byte_equivalence_under_role_refs_reorder(event_loop) -> None:
    """Hash determinism (D75): role_refs sorted by role_id at the use case layer."""
    role_a = UUID("00000000-0000-4000-8000-0000000c0001")
    role_b = UUID("00000000-0000-4000-8000-0000000c0002")
    repo1 = _FakeMethodologyRepository()
    repo2 = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()
    _, rev1 = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo1,
            security_events=sec,
            name="HashEq",
            description="ordering test",
            role_refs=(_role_ref(role_id=role_a), _role_ref(role_id=role_b)),
            actor_user_id="alice",
        )
    )
    _, rev2 = event_loop.run_until_complete(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo2,
            security_events=sec,
            name="HashEq",
            description="ordering test",
            role_refs=(_role_ref(role_id=role_b), _role_ref(role_id=role_a)),
            actor_user_id="alice",
        )
    )
    assert rev1.this_revision_hash == rev2.this_revision_hash


# ---------------------------------------------------------------------
# D87 byte-equivalence and canonical-encoder tests.
#
# After S26b's D87 refactor, ``RoleRef.overrides`` is typed
# ``dict[str, dict[str, Any]]`` defaulted to an empty dict. The
# canonical-JSON encoder at ``_role_ref_to_canonical`` maps empty
# overrides to ``None`` so methodology hashes computed pre-D87 (LVT
# methodology authored at S25 with overrides=None) remain byte-stable
# post-refactor. The byte-equivalence test below pins this invariant.
# ---------------------------------------------------------------------


def test_empty_overrides_canonicalise_to_none_for_byte_stability() -> None:
    """LVT methodology (empty overrides) hashes byte-equivalent post-D87."""
    from contexts.methodology.application.use_cases import (
        _content_payload,
        _role_ref_to_canonical,
    )

    ref = RoleRef(role_id=_DEFAULT_ROLE_ID, role_version=1)
    canonical = _role_ref_to_canonical(ref)
    assert canonical["overrides"] is None

    # Methodology hash payload spans ``role_refs`` sorted by role_id;
    # for the LVT no-op case the canonical bytes match the pre-D87
    # shape verbatim (overrides null inside each entry).
    payload = _content_payload(
        name="LVT",
        description="Lean Value Tree methodology",
        role_refs=(ref,),
    )
    assert payload["role_refs"][0]["overrides"] is None


def test_populated_overrides_pass_through_canonical_form() -> None:
    """Populated D87 overrides preserve their structured shape canonically."""
    from contexts.methodology.application.use_cases import (
        _role_ref_to_canonical,
    )

    overrides = {
        "system_prompt": {
            "mode": "augment",
            "value": "Apply the SCQ framework when framing",
        },
    }
    ref = RoleRef(
        role_id=_DEFAULT_ROLE_ID,
        role_version=1,
        overrides=overrides,
    )
    canonical = _role_ref_to_canonical(ref)
    assert canonical["overrides"] == overrides


def test_methodology_create_with_populated_overrides_hashes_distinctly() -> None:
    """An override-populated revision hash differs from the empty case."""
    role_id = uuid4()
    repo_empty = _FakeMethodologyRepository()
    repo_populated = _FakeMethodologyRepository()
    sec = _CollectingSecurityEvents()

    _, rev_empty = asyncio.run(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo_empty,
            security_events=sec,
            name="HashOverridesDiffer",
            description="d87",
            role_refs=(RoleRef(role_id=role_id, role_version=1),),
            actor_user_id="alice",
        )
    )
    _, rev_populated = asyncio.run(
        create_methodology_template(
            principal=_operator_principal(),
            repository=repo_populated,
            security_events=sec,
            name="HashOverridesDiffer",
            description="d87",
            role_refs=(
                RoleRef(
                    role_id=role_id,
                    role_version=1,
                    overrides={
                        "system_prompt": {
                            "mode": "augment",
                            "value": "specialise for X",
                        },
                    },
                ),
            ),
            actor_user_id="alice",
        )
    )
    assert rev_empty.this_revision_hash != rev_populated.this_revision_hash
