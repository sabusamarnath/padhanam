"""Single-source-of-truth contract for intent-classification primitive (D137, S48b).

The intent-classification evaluation substrate at D137 requires the
evaluation runner to call the structured-output port with the same
prompt and schema the production cell uses. Otherwise the substrate
measures a different prompt's classifications and the load-bearing
claim ("substrate measures production component-quality") fails.

This contract test binds the single-source-of-truth claim
structurally: every consumer of ``INTENT_EXTRACTION_SCHEMA`` and
``build_extraction_prompt`` must resolve to the same object as the
shared_kernel canonical definition. Drift between consumer copies
(or accidentally-re-defined locals) is caught at CI rather than at
production-runtime divergence.

Second instance of the structural-test-binding methodology pattern.
First instance was the no-numeric-threshold-literals AST test at S47
addendum commit 4f74509 (ThresholdResolver port substrate). Both
bind a load-bearing architectural claim in CI rather than relying on
convention or reviewer attention.
"""

from __future__ import annotations


def test_messaging_cell_imports_resolve_to_shared_kernel_schema() -> None:
    """The cell's INTENT_EXTRACTION_SCHEMA reference is the shared one.

    Asserts Python identity (`is`) rather than value equality —
    proves the cell does not carry an accidental local copy that
    would diverge silently as one side is edited.
    """
    from contexts.messaging.application import manual_entry_cell
    from shared_kernel.intent_classification import INTENT_EXTRACTION_SCHEMA

    assert manual_entry_cell.INTENT_EXTRACTION_SCHEMA is INTENT_EXTRACTION_SCHEMA


def test_messaging_cell_imports_resolve_to_shared_kernel_prompt_builder() -> None:
    """The cell's build_extraction_prompt reference is the shared one."""
    from contexts.messaging.application import manual_entry_cell
    from shared_kernel.intent_classification import build_extraction_prompt

    assert manual_entry_cell.build_extraction_prompt is build_extraction_prompt


def test_messaging_domain_intent_reexports_shared_schema() -> None:
    """contexts/messaging/domain/intent.py re-exports the shared schema.

    Backward-compat: tests and other consumers that import from
    contexts.messaging.domain.intent must still see the same
    canonical schema object.
    """
    from contexts.messaging.domain import intent as messaging_intent_module
    from shared_kernel.intent_classification import INTENT_EXTRACTION_SCHEMA

    assert messaging_intent_module.INTENT_EXTRACTION_SCHEMA is INTENT_EXTRACTION_SCHEMA


def test_intent_classification_evaluation_runner_consumes_shared_primitive() -> (
    None
):
    """The evaluation runner's prompt/schema reference is the shared one.

    Imports lazily because the runner ships at a later S48b commit;
    the test asserts the contract once the runner module is in place.
    Until the runner ships, this test is xfail-safe by import guard.
    """
    try:
        from contexts.intent_classification_evaluation.application import (
            run_intent_classification_evaluation as runner_module,
        )
    except ImportError:
        # Runner not yet shipped at this commit; the contract activates
        # at the runner-ships commit. The other three tests above bind
        # the cell-side single-source-of-truth claim now.
        return

    from shared_kernel.intent_classification import (
        INTENT_EXTRACTION_SCHEMA,
        build_extraction_prompt,
    )

    assert runner_module.INTENT_EXTRACTION_SCHEMA is INTENT_EXTRACTION_SCHEMA
    assert runner_module.build_extraction_prompt is build_extraction_prompt
