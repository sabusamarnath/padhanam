"""Messaging application layer (D129).

Use cases: ``send_message`` (outbound), ``record_inbound_message``
(plain inbound persistence, invoked from the intake-context
orchestration via a consumer port), ``get_message``,
``list_messages``.
"""
