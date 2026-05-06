"""ModelConfig value object — evaluation's model-selection shape.

The replay engine and the prompt applier both choose what model to
invoke against. ``ModelConfig`` lives in evaluation's domain rather
than crossing into ``contexts/inference/``'s domain so cross-context
coupling stays at the adapter layer where D16 wants it: the
inference adapter at
``contexts/evaluation/adapters/outbound/inference_adapter.py``
translates ``ModelConfig`` into whatever the inference call expects
(currently ``model: str | None``). If a second consumer surfaces
later (the agent runtime at P8 might need the same shape), the
location can be reassessed against D16's "shared_kernel contains
only types that must be referentially equal across contexts"; at
one consumer (evaluation), domain-local placement is right.

Forward-affordance discipline: ``temperature`` and ``max_tokens``
are placeholders that the current inference port does not consume.
S17a does not surface them through to the LiteLLM call (the port
shape ``model: str | None`` does not carry sampling parameters);
they exist on the value object so judge-prompt configuration can
land them at the data layer when the inference port shape grows.
The S17b reflection paragraph or a future session decides whether
to route them through.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    model_name: str
    temperature: float = 0.7
    max_tokens: int | None = None
