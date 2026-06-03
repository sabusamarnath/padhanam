"""Threshold-briefing bounded context (D153, P15, S57).

The proactive arc on the BroadcastFlow machinery (D142/D143). Holds two
BroadcastFlow implementers in a two-stage chain plus the configured-rules
schema:

- ``ThresholdEvaluator`` (registered under the ``SCHEDULED_EVALUATION``
  trigger type): refresh-then-evaluate — sync the active-rule substrates
  through a consumer refresh port, then evaluate over the calendar STATE
  STORE (not the audit chain; D153) against configured rules, emitting
  ``THRESHOLD_CROSSED`` on a match through a consumer emitter port wired
  to the D147 FireTrigger idempotency flow.
- ``ThresholdBriefingImplementer`` (registered under ``THRESHOLD_CROSSED``):
  compose, render, and dispatch the briefing for a crossing.

Both implementers depend only on shared_kernel plus this context's
consumer ports; the apps composition root bridges the ports to calendar
(refresh, state read), messaging (emit, notify), and the LLM (compose).
The two-threshold rule keeps the evaluator and the briefing in one context
until a second proactive surface forces a split.
"""
