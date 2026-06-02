"""calendar_conversation consumer ports.

The cell consumes calendar's ``MeetingReader`` directly (the audit-
conversation precedent of consuming the producer context's existing
reader rather than introducing a parallel port). The calendar refresh
port (D150 refresh-before-answer) lands here at S55b-1 commit 3.
"""
