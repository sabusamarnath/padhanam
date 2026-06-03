"""Run-intent-classification-evaluation use case (D137, S48b).

Orchestration: load gold set; create EvaluationRun in running status;
for each gold-set entry call the structured-output port at the
runner's model_hint; record per-entry EvaluationResult; compute
per-class EvaluationAggregate records; mark the run completed.
Per-entry parse failures are captured as parse_failure=True results
rather than failing the whole run; the run itself fails only on
unrecoverable inference errors (timeouts the runner cannot retry,
configuration errors).

The runner calls ``StructuredOutputPort.generate_structured`` directly
without the messaging cell or the dispatch port — Surface 8's
component-isolation discipline binds here. The prompt and schema
come from ``shared_kernel.intent_classification`` (the same the
production cell uses).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.audit.domain.ports import AuditPort
from contexts.intent_classification_evaluation.application.audit_events import (
    draft_run_complete,
    draft_run_fail,
    draft_run_start,
)
from contexts.intent_classification_evaluation.domain.evaluation_result import (
    EvaluationResult,
)
from contexts.intent_classification_evaluation.domain.evaluation_run import (
    EvaluationRun,
    EvaluationRunStatus,
    utcnow,
)
from contexts.intent_classification_evaluation.domain.metrics import (
    compute_aggregates,
    compute_is_correct,
)
from contexts.intent_classification_evaluation.ports.gold_set_reader import (
    GoldSetReader,
)
from contexts.intent_classification_evaluation.ports.repository import (
    EvaluationRunRepository,
)
from shared_kernel import (
    ActorContext,
    LatencyTier,
    StructuredOutputParseFailure,
    StructuredOutputPort,
    StructuredOutputRequest,
    TenantContext,
)
from shared_kernel.inference import (
    DEFAULT_ACCOUNT,
    ModelConfiguration,
    ModelIdentifier,
    Provider,
)
from shared_kernel.intent_classification import (
    INTENT_EXTRACTION_SCHEMA,
    build_extraction_prompt,
)
from shared_kernel.intent_classification_audit import (
    AUDIT_INTENT_EXTRACTION_SCHEMA,
    build_audit_extraction_prompt,
)
from shared_kernel.intent_classification_calendar import (
    CALENDAR_INTENT_EXTRACTION_SCHEMA,
    build_calendar_extraction_prompt,
)
from shared_kernel.intent_classification_email import (
    EMAIL_INTENT_EXTRACTION_SCHEMA,
    build_email_extraction_prompt,
)
from shared_kernel.intent_classification_mirror import (
    MIRROR_INTENT_EXTRACTION_SCHEMA,
    build_mirror_extraction_prompt,
)
from shared_kernel.meta_classification import (
    META_CLASSIFIER_SCHEMA,
    build_meta_classifier_prompt,
)


def _build_meta_classifier_prompt_unary(message: str) -> str:
    """Wrap meta-classifier prompt for the runner's single-arg shape.

    The runner calls each surface's prompt builder as
    ``builder(entry.input_phrasing)``; the meta-classifier's natural
    signature also accepts conversation history. For the gold-set
    evaluation runner, every entry is treated as a fresh first-turn
    inbound with no prior history (the gold set's inputs are
    self-contained phrasings).
    """
    return build_meta_classifier_prompt(inbound_text=message)


# Per-surface (prompt_builder, schema, result_key) lookup. S51 added the
# audit_conversation surface alongside manual_entry; S52 adds the
# dispatch_classifier surface (the D140 meta-classifier) and the
# mirror_conversation surface. Result keys differ per schema:
# manual_entry → ``intent_type``; audit_conversation → ``intent_class``;
# dispatch_classifier → ``cell_identifier``; mirror_conversation →
# ``intent_class`` (mirror prompt+schema land at S52 commit 8/9).
# Future ConversationFlow implementers extend this dict at the same
# pattern; full parameterisation refactor activates at the deferred-
# decisions trigger.
_SURFACE_PRIMITIVES: dict[str, tuple[Any, dict, str]] = {
    "manual_entry": (
        build_extraction_prompt,
        INTENT_EXTRACTION_SCHEMA,
        "intent_type",
    ),
    "audit_conversation": (
        build_audit_extraction_prompt,
        AUDIT_INTENT_EXTRACTION_SCHEMA,
        "intent_class",
    ),
    "dispatch_classifier": (
        _build_meta_classifier_prompt_unary,
        META_CLASSIFIER_SCHEMA,
        "cell_identifier",
    ),
    "mirror_conversation": (
        build_mirror_extraction_prompt,
        MIRROR_INTENT_EXTRACTION_SCHEMA,
        "intent_class",
    ),
    "calendar_conversation": (
        build_calendar_extraction_prompt,
        CALENDAR_INTENT_EXTRACTION_SCHEMA,
        "intent_class",
    ),
    "email_conversation": (
        build_email_extraction_prompt,
        EMAIL_INTENT_EXTRACTION_SCHEMA,
        "intent_class",
    ),
}


@dataclass(frozen=True)
class RunIntentClassificationEvaluationCommand:
    """Inputs for the run-evaluation use case."""

    gold_set_name: str
    model: str  # the model identifier from the registry (e.g. "gpt-4o-mini")
    latency_tier: LatencyTier = LatencyTier.REAL_TIME_REQUIRED


@dataclass(frozen=True)
class RunIntentClassificationEvaluationResult:
    """Outputs from the run-evaluation use case."""

    run_id: UUID
    status: EvaluationRunStatus
    total_entries: int
    correct_count: int
    parse_failure_count: int


def _infer_provider(model: str) -> Provider:
    """Infer the D132 Provider layer from a model identifier string.

    Mirrors the logic at
    ``contexts.inference.adapters.outbound.litellm.model_ontology.provider_for_model``.
    Duplicated here rather than imported because the LiteLLM adapter
    is a sibling concern; the evaluation runner does not depend on
    the inference adapter's internals.
    """
    lowered = model.lower()
    if lowered.startswith(("gpt-", "o1", "o3")):
        return Provider.OPENAI
    if lowered.startswith("claude"):
        return Provider.ANTHROPIC
    return Provider.OLLAMA


async def run_intent_classification_evaluation(
    command: RunIntentClassificationEvaluationCommand,
    *,
    gold_set_reader: GoldSetReader,
    structured_output_port: StructuredOutputPort,
    repository: EvaluationRunRepository,
    audit_port: AuditPort,
    tenant: TenantContext,
    actor: ActorContext,
) -> RunIntentClassificationEvaluationResult:
    """Execute an evaluation run end-to-end."""
    gold_set = gold_set_reader.get_gold_set(command.gold_set_name)

    # Look up the (prompt_builder, schema, result_key) primitive for the
    # gold-set's intent_surface (S51 parameterisation).
    if gold_set.intent_surface not in _SURFACE_PRIMITIVES:
        raise ValueError(
            f"gold-set {gold_set.name!r} declares intent_surface "
            f"{gold_set.intent_surface!r} which is not in "
            f"{list(_SURFACE_PRIMITIVES)}; add a surface primitive entry."
        )
    prompt_builder, schema, result_key = _SURFACE_PRIMITIVES[
        gold_set.intent_surface
    ]

    model_identifier = ModelIdentifier(
        provider=_infer_provider(command.model),
        account=DEFAULT_ACCOUNT,
        version=command.model,
        configuration=ModelConfiguration(
            latency_tier=command.latency_tier,
            temperature=0.0,
            max_tokens=None,
            structured_output_schema=schema,
        ),
    )

    run = EvaluationRun(
        id=uuid4(),
        tenant_id=tenant.tenant_id,
        gold_set_name=gold_set.name,
        model_identifier=model_identifier,
        status=EvaluationRunStatus.RUNNING,
        started_at=utcnow(),
        completed_at=None,
        failure_reason=None,
    )

    await repository.create_run(run, tenant=tenant)
    await audit_port.emit(
        draft_run_start(
            tenant_context=tenant, run=run, actor=str(actor.actor_id)
        )
    )

    results: list[EvaluationResult] = []
    try:
        for entry_index, entry in enumerate(gold_set.entries):
            result = await _classify_one_entry(
                run_id=run.id,
                entry_index=entry_index,
                entry=entry,
                model=command.model,
                latency_tier=command.latency_tier,
                structured_output_port=structured_output_port,
                prompt_builder=prompt_builder,
                schema=schema,
                result_key=result_key,
            )
            await repository.append_result(result, tenant=tenant)
            results.append(result)
    except Exception as e:  # noqa: BLE001 — runner-level failure surface
        # An unrecoverable failure at the runner level (timeout the
        # adapter raised after exhausting its retry budget; config
        # error). Per-entry parse failures are caught inside
        # _classify_one_entry and recorded as parse_failure=True
        # without reaching here.
        failed_run = run.mark_failed(at=utcnow(), reason=str(e)[:500])
        await repository.update_run(failed_run, tenant=tenant)
        await audit_port.emit(
            draft_run_fail(
                tenant_context=tenant,
                run=failed_run,
                actor=str(actor.actor_id),
            )
        )
        return RunIntentClassificationEvaluationResult(
            run_id=run.id,
            status=EvaluationRunStatus.FAILED,
            total_entries=len(gold_set.entries),
            correct_count=sum(1 for r in results if r.is_correct),
            parse_failure_count=sum(1 for r in results if r.parse_failure),
        )

    aggregates = compute_aggregates(run_id=run.id, results=tuple(results))
    await repository.write_aggregates(aggregates, tenant=tenant)

    completed_run = run.mark_completed(at=utcnow())
    await repository.update_run(completed_run, tenant=tenant)
    await audit_port.emit(
        draft_run_complete(
            tenant_context=tenant,
            run=completed_run,
            actor=str(actor.actor_id),
        )
    )

    return RunIntentClassificationEvaluationResult(
        run_id=run.id,
        status=EvaluationRunStatus.COMPLETED,
        total_entries=len(gold_set.entries),
        correct_count=sum(1 for r in results if r.is_correct),
        parse_failure_count=sum(1 for r in results if r.parse_failure),
    )


async def _classify_one_entry(
    *,
    run_id: UUID,
    entry_index: int,
    entry,  # type: IntentClassificationGoldSetEntry
    model: str,
    latency_tier: LatencyTier,
    structured_output_port: StructuredOutputPort,
    prompt_builder: Any = build_extraction_prompt,
    schema: dict = INTENT_EXTRACTION_SCHEMA,
    result_key: str = "intent_type",
) -> EvaluationResult:
    """Classify a single gold-set entry and return the result.

    Per-entry parse failures (per D134's StructuredOutputParseFailure)
    are recorded as ``parse_failure=True`` with empty
    classified_intent_class; they do not fail the run.

    ``prompt_builder``, ``schema``, and ``result_key`` are parametric
    over the gold-set's intent_surface (S51 parameterisation). Defaults
    preserve manual_entry behaviour for backward compatibility with
    callers that pre-date the parameterisation.
    """
    request = StructuredOutputRequest(
        prompt=prompt_builder(entry.input_phrasing),
        schema=schema,
        latency_tier=latency_tier,
        temperature=0.0,
        model_hint=model,
    )

    start = time.monotonic()
    try:
        response = await structured_output_port.generate_structured(request)
    except StructuredOutputParseFailure:
        latency_ms = int((time.monotonic() - start) * 1000)
        return EvaluationResult(
            run_id=run_id,
            entry_index=entry_index,
            input_phrasing=entry.input_phrasing,
            expected_intent_class=entry.expected_intent_class,
            classified_intent_class="",
            confidence=None,
            latency_ms=latency_ms,
            parse_failure=True,
            is_correct=False,
        )
    latency_ms = int((time.monotonic() - start) * 1000)

    classified_intent_class = str(
        response.value.get(result_key, "")
    ).strip()
    is_correct = compute_is_correct(
        expected_intent_class=entry.expected_intent_class,
        classified_intent_class=classified_intent_class,
        confidence=response.confidence,
        expected_confidence_minimum=entry.expected_confidence_minimum,
        parse_failure=False,
    )

    return EvaluationResult(
        run_id=run_id,
        entry_index=entry_index,
        input_phrasing=entry.input_phrasing,
        expected_intent_class=entry.expected_intent_class,
        classified_intent_class=classified_intent_class,
        confidence=response.confidence,
        latency_ms=latency_ms,
        parse_failure=False,
        is_correct=is_correct,
    )


__all__ = [
    "RunIntentClassificationEvaluationCommand",
    "RunIntentClassificationEvaluationResult",
    "run_intent_classification_evaluation",
]
