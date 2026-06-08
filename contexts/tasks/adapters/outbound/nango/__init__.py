"""Nango Proxy outbound adapter for the tasks context (D167).

The single place the tasks context speaks Google Tasks' wire format and Nango
Proxy's headers. The application depends on ``TaskSourcePort``; the apps/
composition root wires this adapter in.
"""
