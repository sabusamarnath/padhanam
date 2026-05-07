"""LiteLLM extraction adapter for the ingestion context (D64).

The third place ``litellm`` enters the codebase, alongside the
chat adapter at ``contexts.inference.adapters.outbound.litellm``
and the embedding adapter at
``contexts.ingestion.adapters.outbound.embedding``. The
``litellm-confined`` import-linter contract extends to admit this
directory.
"""

from contexts.ingestion.adapters.outbound.extraction.litellm_extractor import (
    LiteLLMEntityExtractor,
)

__all__ = ["LiteLLMEntityExtractor"]
