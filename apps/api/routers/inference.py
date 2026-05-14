"""POST /inference/completions router.

The handler is thin: it validates the Pydantic request, resolves a
``TenantContext`` from the control-plane registry against the
authenticated principal's tenant_id (S15), and calls
``contexts.inference.api.request_completion`` with the context. No
business logic.

The InferencePort is wired at app construction time
(``apps/api/main.py``) and stashed on app.state so handlers can fetch
it via the dependency function below; this keeps the handler
signature pure FastAPI/Pydantic and the wiring composition out of the
context.

TenantContext resolution (S15)
------------------------------
``get_tenant_context`` is the FastAPI dependency that bridges the
authenticated principal to the registry-resolved context. The
principal's ``tenant_id`` is UUID-shaped (the dev-token issuer in
``padhanam.security.auth`` enforces this when issued for tenant
context); the dependency parses it, calls ``registry.get_tenant``,
returns 404 if absent, and constructs ``TenantContext`` from the
returned ``Tenant``. Tests substitute via FastAPI's
``app.dependency_overrides[get_tenant_context]``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from apps.api.middleware import get_principal
from contexts.inference.api import Message, request_completion
from contexts.inference.domain.errors import (
    InferenceConfigurationError,
    InferenceTimeout,
    InferenceUnavailable,
)
from contexts.inference.ports import InferencePort
from contexts.tenancy.domain.tenant_id import TenantId
from shared_kernel import TenantContext
from padhanam.security import Principal, PrincipalType

router = APIRouter(prefix="/inference", tags=["inference"])


class CompletionMessage(BaseModel):
    role: str = Field(min_length=1)
    content: str


class CompletionRequest(BaseModel):
    messages: list[CompletionMessage] = Field(min_length=1)
    model: str | None = None


class CompletionResponse(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    trace_id: str | None = None
    finish_reason: str | None = None


def get_inference_port(request: Request) -> InferencePort:
    """FastAPI dependency: pull the configured InferencePort off app.state.

    apps/api/main.py registers the LiteLLMAdapter (or any other
    InferencePort implementation) on app.state.inference_port at
    application factory time. Handlers depend on this seam so
    composition stays out of the context layer.
    """
    port: InferencePort = request.app.state.inference_port
    return port


async def get_tenant_context(
    request: Request,
    principal: Annotated[Principal, Depends(get_principal)],
) -> TenantContext:
    """Resolve the full TenantContext from the registry at request time.

    Operator-context callers (no rich tenant identity in the registry)
    are not the target of this resolver; per D34 the registry holds
    tenant rows, not operator rows. A principal with tenant_id that is
    not UUID-shaped (e.g., the operator sentinel) returns 400. A UUID
    that is not in the registry returns 404.

    D103 (S37) extends this resolver with a discriminator check at
    entry: platform-operator-typed principals raise
    ``PrincipalTypeMismatchError``, which the registered handler at
    ``apps/api/_auth_errors.py`` (D104, S38) translates to HTTP 403
    plus an ``AUTHZ_DENIAL`` security event.

    Tests override this dependency via ``app.dependency_overrides`` to
    inject a fixed TenantContext when the registry is not wired.
    """
    # Lazy import preserves the prior circular-import guard shape:
    # ``apps.api.routers`` modules are imported by ``apps.api.main``
    # at composition time, and the auth-error module pulls in the
    # shared ``ErrorResponse`` from ``apps.api._errors``. Containing
    # the dependency edge inside the function call avoids load-time
    # cycles.
    from apps.api._auth_errors import PrincipalTypeMismatchError

    if principal.principal_type is not PrincipalType.TENANT:
        raise PrincipalTypeMismatchError(
            required=PrincipalType.TENANT.value,
            actual=principal.principal_type.value,
        )

    registry = getattr(request.app.state, "tenant_registry", None)
    if registry is None:
        raise HTTPException(
            status_code=503, detail="tenant registry not configured"
        )

    try:
        tenant_id_obj = TenantId(str(principal.tenant_id))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                f"principal.tenant_id={principal.tenant_id!r} is not "
                "UUID-shaped; tenant context resolution requires a UUID"
            ),
        )

    tenant = await registry.get_tenant(tenant_id_obj)
    if tenant is None:
        raise HTTPException(
            status_code=404,
            detail=f"tenant {principal.tenant_id} not found",
        )

    return TenantContext(
        tenant_id=str(tenant.id),
        jurisdiction=str(tenant.jurisdiction),
        cost_attribution_id=tenant.cost_attribution_id,
    )


@router.post("/completions", response_model=CompletionResponse)
def completions(
    body: CompletionRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    port: Annotated[InferencePort, Depends(get_inference_port)],
) -> CompletionResponse:
    try:
        completion = request_completion(
            port=port,
            messages=[
                Message(role=m.role, content=m.content) for m in body.messages
            ],
            model=body.model,
            tenant_context=tenant_context,
        )
    except InferenceConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InferenceTimeout as e:
        raise HTTPException(status_code=504, detail=str(e)) from e
    except InferenceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return CompletionResponse(
        text=completion.text,
        model=completion.model,
        input_tokens=completion.usage.input_tokens,
        output_tokens=completion.usage.output_tokens,
        total_tokens=completion.usage.total_tokens,
        trace_id=completion.trace_id,
        finish_reason=completion.finish_reason,
    )
