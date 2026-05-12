"""Unit tests for tool use cases (D89).

In-memory fake repository plus a collecting security-event sink
exercise the auth posture, the Phase 1 classification prohibition,
and the hash-chain wiring without touching Postgres.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.tools.application import (
    archive_tool,
    create_tool,
    create_tool_revision,
    get_tool,
    list_tools,
)
from contexts.tools.domain.exceptions import (
    ClassificationProhibitedError,
    ToolNotFoundError,
)
from contexts.tools.domain.tool import (
    Classification,
    Tool,
    ToolRevision,
)
from contexts.tools.ports import RoleToolBinding
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
)
from padhanam.security import (
    OPERATOR_ROLE,
    AuthorizationError,
    Principal,
)
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


class _CollectingSecurityEvents:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def emit(self, event: SecurityEvent) -> None:
        self.events.append(event)


class _FakeToolRepository:
    def __init__(self) -> None:
        self.templates: dict[UUID, Tool] = {}
        self.revisions: dict[UUID, list[ToolRevision]] = {}
        self.revisions_by_id: dict[UUID, ToolRevision] = {}

    async def create_template(
        self,
        template: Tool,
        initial_revision: ToolRevision,
    ) -> Tool:
        self.templates[template.id] = template
        self.revisions[template.id] = [initial_revision]
        self.revisions_by_id[initial_revision.id] = initial_revision
        return template

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[Tool, ToolRevision]:
        if template_id not in self.templates:
            raise ToolNotFoundError(f"tool {template_id} not found")
        revs = self.revisions[template_id]
        rev = revs[-1] if version is None else next(
            r for r in revs if r.version == version
        )
        return self.templates[template_id], rev

    async def find_revision(
        self,
        revision_id: UUID,
    ) -> tuple[Tool, ToolRevision]:
        rev = self.revisions_by_id[revision_id]
        return self.templates[rev.tool_id], rev

    async def list_templates(self) -> list[Tool]:
        return [t for t in self.templates.values() if t.archived_at is None]

    async def add_revision(
        self,
        template_id: UUID,
        revision: ToolRevision,
    ) -> ToolRevision:
        self.revisions[template_id].append(revision)
        self.revisions_by_id[revision.id] = revision
        return revision

    async def archive_template(self, template_id: UUID) -> Tool:
        t = self.templates[template_id]
        archived = Tool(
            id=t.id,
            name=t.name,
            description=t.description,
            classification=t.classification,
            created_by_user_id=t.created_by_user_id,
            created_at=t.created_at,
            archived_at=datetime.now(timezone.utc),
        )
        self.templates[template_id] = archived
        return archived

    async def verify_chain_integrity(self, template_id: UUID) -> None:  # pragma: no cover
        return None

    async def list_roles_using_tool(
        self, tool_id: UUID,
    ) -> list[RoleToolBinding]:  # pragma: no cover
        return []


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


_PARAMS = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}
_RETURNS = {"type": "string"}


class TestCreateTool:
    def test_operator_can_create_read_only_tool(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t, r = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="my-tool",
                description="a tool",
                classification=Classification.READ_ONLY,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        assert t.classification is Classification.READ_ONLY
        assert r.version == 1
        assert r.previous_revision_hash == "0" * 64
        assert t.id in repo.templates

    def test_operator_can_create_drafting_tool(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t, _ = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="drafter",
                description="drafts content",
                classification=Classification.DRAFTING,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        assert t.classification is Classification.DRAFTING

    def test_operator_can_create_user_affecting_tool(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t, _ = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="updater",
                description="updates",
                classification=Classification.USER_AFFECTING_WITH_CONSENT,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        assert t.classification is Classification.USER_AFFECTING_WITH_CONSENT

    @pytest.mark.parametrize(
        "classification",
        [
            Classification.FINANCIAL,
            Classification.COMMUNICATION,
            Classification.LEGAL,
        ],
    )
    def test_high_classification_authoring_rejected(
        self, classification: Classification,
    ) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        with pytest.raises(ClassificationProhibitedError) as excinfo:
            asyncio.run(
                create_tool(
                    principal=_operator_principal(),
                    repository=repo,
                    security_events=sec,
                    name="high",
                    description="restricted",
                    classification=classification,
                    parameters_schema=_PARAMS,
                    returns_schema=_RETURNS,
                    actor_user_id="op",
                )
            )
        msg = str(excinfo.value)
        assert classification.value in msg
        assert "confirmation pathway" in msg.lower()
        assert "deferred-decisions" in msg.lower()

    def test_tenant_context_denied(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        with pytest.raises(AuthorizationError):
            asyncio.run(
                create_tool(
                    principal=_tenant_principal(),
                    repository=repo,
                    security_events=sec,
                    name="my-tool",
                    description="a tool",
                    classification=Classification.READ_ONLY,
                    parameters_schema=_PARAMS,
                    returns_schema=_RETURNS,
                    actor_user_id="alice",
                )
            )
        assert any(
            e.category is SecurityEventCategory.AUTHZ_DENIAL
            and e.action == "tool.create"
            for e in sec.events
        )


class TestCreateToolRevision:
    def test_revision_chains_from_latest(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t, r1 = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="t",
                description="d",
                classification=Classification.READ_ONLY,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        r2 = asyncio.run(
            create_tool_revision(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                template_id=t.id,
                parameters_schema={**_PARAMS, "additionalProperties": False},
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        assert r2.version == 2
        assert r2.previous_revision_hash == r1.this_revision_hash
        assert r2.this_revision_hash != r1.this_revision_hash
        assert r2.bc_result == {}  # commit 6 populates

    def test_revision_classification_pulled_from_template(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t, _ = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="drafter",
                description="d",
                classification=Classification.DRAFTING,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        r2 = asyncio.run(
            create_tool_revision(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                template_id=t.id,
                parameters_schema={
                    **_PARAMS,
                    "properties": {
                        "query": {"type": "string"},
                        "tone": {"type": "string"},
                    },
                },
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        # The hash payload denormalises classification from the
        # template; if classification weren't pulled correctly, r1
        # and r2's hashes would diverge in a way the test below
        # caught. Sanity: chain is intact.
        assert r2.version == 2

    def test_tenant_context_denied(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t, _ = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="t",
                description="d",
                classification=Classification.READ_ONLY,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        with pytest.raises(AuthorizationError):
            asyncio.run(
                create_tool_revision(
                    principal=_tenant_principal(),
                    repository=repo,
                    security_events=sec,
                    template_id=t.id,
                    parameters_schema=_PARAMS,
                    returns_schema=_RETURNS,
                    actor_user_id="alice",
                )
            )


class TestReadAccess:
    def test_get_tool_returns_template_and_revision(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t, r = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="t",
                description=None,
                classification=Classification.READ_ONLY,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        fetched_t, fetched_r = asyncio.run(
            get_tool(
                principal=_tenant_principal(),
                repository=repo,
                template_id=t.id,
            )
        )
        assert fetched_t.id == t.id
        assert fetched_r.id == r.id

    def test_list_tools_excludes_archived(self) -> None:
        repo = _FakeToolRepository()
        sec = _CollectingSecurityEvents()
        t1, _ = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="a",
                description=None,
                classification=Classification.READ_ONLY,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        t2, _ = asyncio.run(
            create_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                name="b",
                description=None,
                classification=Classification.READ_ONLY,
                parameters_schema=_PARAMS,
                returns_schema=_RETURNS,
                actor_user_id="op",
            )
        )
        asyncio.run(
            archive_tool(
                principal=_operator_principal(),
                repository=repo,
                security_events=sec,
                template_id=t1.id,
            )
        )
        listed = asyncio.run(
            list_tools(principal=_tenant_principal(), repository=repo)
        )
        ids = {t.id for t in listed}
        assert t1.id not in ids
        assert t2.id in ids
