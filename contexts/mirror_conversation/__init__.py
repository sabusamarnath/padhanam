"""Mirror-conversation ConversationFlow implementer context (P14, S52).

The second ConversationFlow implementer at P14 close (the first was
the manual entry cell at S46; the audit-conversation implementer
landed at S51). Mirror-conversation answers "what is the current
state of my portfolio?" — listing cases, showing case details,
drilling into data points, navigating to parents and siblings.

The context composes the portfolio context's read substrate (via the
``MirrorPortfolioReader`` consumer port and a cross-context wiring
adapter at ``apps/api/_mirror_portfolio_wiring.py``) with the intent-
classification primitive at D137 and the response composition pattern
at D131/D135/D138.

Drill-down navigation is stateless re-classification per turn against
conversation history per D141: each mirror-conversation outbound
persists ``current_focus_artefact`` in the message's ``cell_payload``
column; the next turn extracts the focus from the prior outbound's
payload to anchor relative-intent resolution. No parallel state
machine alongside PendingClarification at Phase 2-A.

``MirrorConversationResponse`` satisfies ``CitedResponse`` Protocol
(D138) by carrying the three citation tuple fields plus the
``current_focus_artefact`` extension field used by the cell_payload
persistence mechanism per D141.
"""
