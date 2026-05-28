"""Daily-briefing application layer (D146, S54).

Carries the consumer ports (DailyBriefingReader for the composition
reads; the LLM composer port and the BroadcastFlow implementer land at
S54 commit 6) plus, from commit 6, the BroadcastFlow implementer that
registers with the BroadcastFlow registry at composition root.
"""
