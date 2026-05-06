"""Cross-column NULL invariants on ApplierConfig (S16 framing).

Schema-level CHECKs on the applier_type-plus-nullable-columns shape are
out of scope at S16; the domain layer is the only structural protection
against the invariant. These tests verify ``__post_init__`` rejects
every invalid combination and accepts every valid one, which is the
verification surface the framing names.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from contexts.evaluation.domain.applier import ApplierConfig, ApplierType


def _ids() -> tuple:
    return uuid4(), uuid4(), uuid4()


# ---------------------------------------------------------------------
# Acceptance paths: each applier_type with its required columns set.
# ---------------------------------------------------------------------


def test_deterministic_applier_with_function_name_constructs() -> None:
    a, r, c = _ids()
    cfg = ApplierConfig(
        id=a,
        scoring_sheet_revision_id=r,
        criterion_id=c,
        applier_type=ApplierType.DETERMINISTIC,
        deterministic_function_name="exact_match",
    )
    assert cfg.deterministic_function_name == "exact_match"
    assert cfg.prompt_template is None
    assert cfg.judge_model is None


def test_prompt_applier_with_template_and_model_constructs() -> None:
    a, r, c = _ids()
    cfg = ApplierConfig(
        id=a,
        scoring_sheet_revision_id=r,
        criterion_id=c,
        applier_type=ApplierType.PROMPT,
        prompt_template="Score this output: {output}",
        judge_model="qwen2.5:7b",
    )
    assert cfg.prompt_template.startswith("Score")
    assert cfg.judge_model == "qwen2.5:7b"
    assert cfg.deterministic_function_name is None


def test_human_applier_with_no_executable_columns_constructs() -> None:
    a, r, c = _ids()
    cfg = ApplierConfig(
        id=a,
        scoring_sheet_revision_id=r,
        criterion_id=c,
        applier_type=ApplierType.HUMAN,
    )
    assert cfg.deterministic_function_name is None
    assert cfg.prompt_template is None
    assert cfg.judge_model is None


# ---------------------------------------------------------------------
# Rejection paths: every invalid nullable-column combination raises.
# ---------------------------------------------------------------------


def test_deterministic_without_function_name_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="deterministic"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.DETERMINISTIC,
        )


def test_deterministic_with_prompt_template_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="deterministic"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.DETERMINISTIC,
            deterministic_function_name="exact_match",
            prompt_template="not allowed here",
        )


def test_deterministic_with_judge_model_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="deterministic"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.DETERMINISTIC,
            deterministic_function_name="exact_match",
            judge_model="qwen2.5:7b",
        )


def test_prompt_without_template_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="prompt"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.PROMPT,
            judge_model="qwen2.5:7b",
        )


def test_prompt_without_judge_model_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="prompt"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.PROMPT,
            prompt_template="Score this output: {output}",
        )


def test_prompt_with_deterministic_function_name_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="prompt"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.PROMPT,
            prompt_template="Score this output: {output}",
            judge_model="qwen2.5:7b",
            deterministic_function_name="exact_match",
        )


def test_human_with_deterministic_function_name_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="human"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.HUMAN,
            deterministic_function_name="exact_match",
        )


def test_human_with_prompt_template_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="human"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.HUMAN,
            prompt_template="not allowed here",
        )


def test_human_with_judge_model_rejected() -> None:
    a, r, c = _ids()
    with pytest.raises(ValueError, match="human"):
        ApplierConfig(
            id=a,
            scoring_sheet_revision_id=r,
            criterion_id=c,
            applier_type=ApplierType.HUMAN,
            judge_model="qwen2.5:7b",
        )
