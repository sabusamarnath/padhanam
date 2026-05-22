"""Latency tier and four-layer model ontology — inference-port primitives.

D122 commits latency-tier inference routing as a Phase 2-A
architectural primitive; D132 commits the four-layer model ontology
at the inference port. This module carries both as shared_kernel
value objects so every inference-port consumer and adapter speaks
one vocabulary.

``LatencyTier`` is the D122 hint a call site declares — REAL_TIME_REQUIRED
for user-invoked surfaces, ASYNC_TOLERANT for substrate and
background work. The inference-port surface carries it as a
*defaulted* parameter (REAL_TIME_REQUIRED default — Path A, S46
Finding A: D122 commits "Phase 1 call sites preserve current
behaviour with opt-in retrofit", which a required parameter would
violate).

``ModelIdentifier`` is the D132 four-layer identification —
Provider, Account, Version, Configuration. It does *not* sit on the
public inference-port call signature (S46 Finding C: call sites
carry no Provider/Account knowledge, and the Configuration layer
overlaps fields already on the request surface). It composes at the
LiteLLM adapter boundary from the resolved model string, the
latency tier, and ``InferenceSettings``; the adapter consumes it
for tier routing and per-call four-dimension audit/span capture.

Framework-free per D16 — shared_kernel is policed; stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LatencyTier(StrEnum):
    """The D122 latency-tolerance hint a call site declares.

    ``REAL_TIME_REQUIRED`` — user-invoked surfaces plus Tier 1
    confirmation dialogs; a sub-second latency budget, latency-optimised
    model selection. ``ASYNC_TOLERANT`` — substrate ingestion
    analysis, surfacing-decision logic, background judgment work; a
    seconds-to-minutes budget, quality-optimised model selection.
    """

    REAL_TIME_REQUIRED = "real_time_required"
    ASYNC_TOLERANT = "async_tolerant"


class Provider(StrEnum):
    """The D132 Provider layer — the underlying inference service."""

    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


# The Account layer is trivial at Phase 2-A — one account per
# provider — so call sites and the adapter use this sentinel until
# Phase 2-B+ customer deployments make multi-account routing
# load-bearing.
DEFAULT_ACCOUNT = "default"


@dataclass(frozen=True)
class ModelConfiguration:
    """The D132 Configuration layer — per-call parameters.

    ``latency_tier`` is the only required field; ``temperature``,
    ``max_tokens``, and ``structured_output_schema`` are present only
    when the call sets them. ``structured_output_schema`` is the
    JSON Schema dict for a D130 structured-output call.
    """

    latency_tier: LatencyTier
    temperature: float | None = None
    max_tokens: int | None = None
    structured_output_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class ModelIdentifier:
    """The D132 four-layer model identification at the inference port.

    Provider, Account, Version, Configuration together produce the
    procurement-grade defensibility surface: an auditor verifying
    which provider, account, version, and configuration served which
    operation has a complete identification path. ``ModelIdentifier``
    composes at the LiteLLM adapter boundary, not at the public call
    signature (S46 Finding C).
    """

    provider: Provider
    account: str
    version: str
    configuration: ModelConfiguration

    def __post_init__(self) -> None:
        if not self.account or not self.account.strip():
            raise ValueError("ModelIdentifier.account must be non-empty")
        if not self.version or not self.version.strip():
            raise ValueError("ModelIdentifier.version must be non-empty")

    def audit_dimensions(self) -> dict[str, str]:
        """The four span attributes for per-call audit capture (D132).

        Every LLM call's OTel span carries these so observability
        surfaces can filter by provider, account, version, and the
        composed configuration.
        """
        cfg = self.configuration
        parts = [f"latency_tier={cfg.latency_tier.value}"]
        if cfg.temperature is not None:
            parts.append(f"temperature={cfg.temperature}")
        if cfg.max_tokens is not None:
            parts.append(f"max_tokens={cfg.max_tokens}")
        parts.append(
            "structured_output_schema="
            + ("present" if cfg.structured_output_schema else "none")
        )
        return {
            "gen_ai.model.provider": self.provider.value,
            "gen_ai.model.account": self.account,
            "gen_ai.model.version": self.version,
            "gen_ai.model.configuration": ";".join(parts),
        }


__all__ = [
    "DEFAULT_ACCOUNT",
    "LatencyTier",
    "ModelConfiguration",
    "ModelIdentifier",
    "Provider",
]
