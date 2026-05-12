"""RoleLookup Protocol port + RoleView DTO (S26a-2 / D86).

Second cross-context lookup port for the agent context, alongside
``MethodologyLookup`` (D79). The agent context's create-from-role
flow needs to read a role template's content at clone time without
taking a domain dependency on the methodology context (D17). The
port is a callable Protocol the wiring layer (apps/cli) implements
as an adapter over
``contexts.methodology.application.use_cases.get_role_template``;
the adapter translates the producer's
(RoleTemplate, RoleRevision) tuple into the consumer-shaped
``RoleView`` frozen dataclass defined here.

The DTO carries exactly the fields the create-from-role use case
consumes: the resolved role id and version (recorded in the cloned
agent's role lineage per D86), the role's description (cloned to the
agent's envelope), and the seven revision-content fields the cloned
revision inherits verbatim. The role's name is intentionally not on
the view because the cloned agent gets its own name from the clone
request, not from the role.

The pattern mirrors MethodologyLookup / MethodologyView from D79
exactly so the two cross-context lookups have consistent shape at
the consumer side; the structural duplication is a second-instance
observation of the api-facade-via-callable pattern from D17 (the
abstraction-promotion test fires at a third consumer per the
methodology-promotion convention).

The RoleView's fields are a subset of the role revision's columns;
the producer-side aggregate exposes additional chain-metadata
(template_id, version on the revision, timestamps, chain pointers)
that the consumer has no business reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Protocol
from uuid import UUID

from padhanam.security import Principal
from shared_kernel import ToolAllowlistEntry


@dataclass(frozen=True)
class RoleView:
    """Consumer-shaped view over a role template + resolved revision.

    All fields are populated by the apps/cli adapter from the
    producer's (RoleTemplate, RoleRevision) tuple at lookup time.
    The view is immutable per the frozen dataclass; the consumer uses
    it to construct the cloned agent's role lineage and revision-1
    content.
    """

    role_id: UUID
    role_version: int
    description: str | None
    system_prompt: str
    tool_allowlist: tuple[ToolAllowlistEntry, ...]
    retrieval_strategy: Mapping[str, Any]
    filter_tree: Mapping[str, Any]
    top_k: int
    min_score: Decimal
    model_selection: str


class RoleLookup(Protocol):
    """Callable port for role lookup at clone time.

    The Protocol is structurally typed: any callable accepting the
    named keyword arguments and returning a RoleView satisfies it.
    The apps/cli adapter at S26a-2 implements this by wrapping
    ``contexts.methodology.application.use_cases.get_role_template``
    and translating its return tuple into a RoleView.

    ``version=None`` resolves to the role template's latest revision;
    the adapter records the resolved integer in the returned view's
    ``role_version`` field so the use case can persist the resolved
    version (not None) in the cloned agent's lineage per D86's
    paired-NULL invariant on the role lineage pair.

    Lookup failure propagates as ``LookupError`` from the underlying
    repository; the use case lets it propagate without re-wrapping
    because the consumer's caller already understands LookupError as
    the platform's not-found convention.
    """

    async def __call__(
        self,
        *,
        role_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> RoleView: ...
