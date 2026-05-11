"""MethodologyLookup Protocol port + MethodologyView DTO (D79).

The agent context's create-from-methodology flow needs to read a
methodology template's content at clone time without taking a domain
dependency on the methodology context (D17). The port is a callable
Protocol the wiring layer (apps/cli) implements as an adapter over
``contexts.methodology.application.use_cases.get_methodology_template``;
the adapter translates the producer's
(MethodologyTemplate, MethodologyRevision) tuple into the consumer-
shaped MethodologyView frozen dataclass defined here.

The DTO carries exactly the fields the create-from-methodology use
case consumes: the resolved template id and version (recorded in the
cloned agent's lineage per D75), the description (cloned to the
agent's envelope), and the seven revision-content fields the cloned
revision inherits verbatim. The methodology's name is intentionally
not on the view because the cloned agent gets its own name from the
clone request, not from the methodology.

The MethodologyView's fields are a subset of the methodology
revision's columns; the producer-side aggregate exposes additional
chain-metadata (template_id, version on the revision, timestamps,
chain pointers) that the consumer has no business reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Protocol
from uuid import UUID

from padhanam.security import Principal


@dataclass(frozen=True)
class MethodologyView:
    """Consumer-shaped view over a methodology template + resolved revision.

    All fields are populated by the apps/cli adapter from the
    producer's (MethodologyTemplate, MethodologyRevision) tuple at
    lookup time. The view is immutable per the frozen dataclass; the
    consumer uses it to construct the cloned agent's lineage and
    revision-1 content.
    """

    methodology_template_id: UUID
    methodology_version: int
    description: str | None
    system_prompt: str
    tool_allowlist: tuple[str, ...]
    retrieval_strategy: Mapping[str, Any]
    filter_tree: Mapping[str, Any]
    top_k: int
    min_score: Decimal
    model_selection: str


class MethodologyLookup(Protocol):
    """Callable port for methodology lookup at clone time.

    The Protocol is structurally typed: any callable accepting the
    named keyword arguments and returning a MethodologyView satisfies
    it. The apps/cli adapter at S25 implements this by wrapping
    ``contexts.methodology.application.use_cases.get_methodology_template``
    and translating its return tuple into a MethodologyView.

    ``version=None`` resolves to the methodology template's latest
    revision; the adapter records the resolved integer in the returned
    view's ``methodology_version`` field so the use case can persist
    the resolved version (not None) in the cloned agent's lineage per
    D79.

    Lookup failure propagates as ``LookupError`` from the underlying
    repository; the use case lets it propagate without re-wrapping
    because the consumer's caller already understands LookupError as
    the platform's not-found convention (matches how ``get_agent``
    propagates LookupError from the repository).
    """

    async def __call__(
        self,
        *,
        template_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> MethodologyView: ...
