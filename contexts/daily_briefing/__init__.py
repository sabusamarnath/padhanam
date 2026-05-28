"""Daily-briefing BroadcastFlow implementer context (P15, S54).

The first BroadcastFlow implementer (D142, D146). Where ConversationFlow
implementers (manual_entry at S46; audit-conversation at S51; mirror-
conversation at S52) answer inbound operator messages, the daily-briefing
implementer fires on a platform-initiated DAILY_SCHEDULED trigger (the
HTTP trigger endpoint at D145, fed by the deployment's external
scheduler) and composes a once-a-day briefing.

Per D146 the briefing composes from three internal data sources over a
configurable window (default 24 hours): recent IntakeRecords, recent
audit events, and active Cases. The composition crosses three producer
contexts (intake, audit, portfolio) through the ``DailyBriefingReader``
consumer port and a cross-context wiring adapter at
``apps/api/_daily_briefing_wiring.py`` — the third instance of the
consumer-port-plus-wiring-adapter pattern (after PortfolioGateway at
S46 and MirrorPortfolioReader at S52).

The "attention framing" the bet's positioning depends on emerges from
how recent changes surface against the current portfolio snapshot; the
forward-looking threshold-briefing escalation lands at S57. Pure
activity-feed shape was rejected at D146 because it loses state context.

``DailyBriefingResponse`` satisfies the ``CitedResponse`` Protocol
(D138) by carrying the three citation tuple fields plus a
``briefing_period`` extension field for the render header.
Cell-payload persistence (D141) does not activate at this first
instance — broadcasts have no user-driven follow-up turns.
"""
