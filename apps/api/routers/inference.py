"""POST /inference/completions router.

The handler is thin: it validates the Pydantic request, extracts the
authenticated principal from request state (set by the auth
middleware), and calls contexts.inference.api.request_completion with
the principal's tenant_id. No business logic.

The InferencePort is wired at app construction time (apps/api/main.py)
and stashed on app.state so handlers can fetch it via the dependency
function below; this keeps the handler signature pure FastAPI/Pydantic
and the wiring composition out of the context.
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
from vadakkan.security import Principal

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


@router.post("/completions", response_model=CompletionResponse)
def completions(
    body: CompletionRequest,
    principal: Annotated[Principal, Depends(get_principal)],
    port: Annotated[InferencePort, Depends(get_inference_port)],
) -> CompletionResponse:
    try:
        completion = request_completion(
            port=port,
            messages=[
                Message(role=m.role, content=m.content) for m in body.messages
            ],
            model=body.model,
            tenant_id=principal.tenant_id,
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
