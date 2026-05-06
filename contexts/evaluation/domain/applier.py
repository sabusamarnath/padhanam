"""Applier configuration domain entity (D53).

An applier is the executable that scores a criterion against an output.
Per D53, the applier model treats deterministic primitives as code (a
small bounded library inside this context) and prompt appliers
(LLM-as-judge) as data records subject to the same authorship and
versioning model as the scoring sheet itself. The human applier mode
exists in the data model only at S16; no UI write path ships per D53.

``ApplierType`` is a stdlib StrEnum, not a Pydantic Literal — domain is
framework-free per D16. ``ApplierConfig`` enforces cross-column NULL
invariants in ``__post_init__`` per the S16 framing decision: schema
CHECKs on the cross-column shape are out of scope at S16; the domain
layer is the only structural protection against the invariant. STI vs
CTI is a watch-item: if S17 prompt-applier addition or future applier
types strain the type-tag-plus-nullable shape, single-table inheritance
promotes to class-table inheritance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ApplierType(StrEnum):
    DETERMINISTIC = "deterministic"
    PROMPT = "prompt"
    HUMAN = "human"


@dataclass(frozen=True)
class ApplierConfig:
    id: UUID
    scoring_sheet_revision_id: UUID
    criterion_id: UUID
    applier_type: ApplierType
    deterministic_function_name: str | None = None
    prompt_template: str | None = None
    judge_model: str | None = None

    def __post_init__(self) -> None:
        if self.applier_type == ApplierType.DETERMINISTIC:
            if self.deterministic_function_name is None:
                raise ValueError(
                    "deterministic applier requires deterministic_function_name"
                )
            if self.prompt_template is not None or self.judge_model is not None:
                raise ValueError(
                    "deterministic applier must not carry prompt_template or judge_model"
                )
        elif self.applier_type == ApplierType.PROMPT:
            if self.prompt_template is None or self.judge_model is None:
                raise ValueError(
                    "prompt applier requires prompt_template and judge_model"
                )
            if self.deterministic_function_name is not None:
                raise ValueError(
                    "prompt applier must not carry deterministic_function_name"
                )
        elif self.applier_type == ApplierType.HUMAN:
            if (
                self.deterministic_function_name is not None
                or self.prompt_template is not None
                or self.judge_model is not None
            ):
                raise ValueError(
                    "human applier must not carry deterministic_function_name, "
                    "prompt_template, or judge_model"
                )
