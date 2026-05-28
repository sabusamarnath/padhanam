"""Nango Proxy outbound adapter for the calendar context (D148).

The single place the calendar context speaks Google Calendar's wire
format and Nango Proxy's headers. No other module imports this; the
application depends on ``CalendarEventSourcePort`` and the apps/
composition root wires this adapter in.
"""
