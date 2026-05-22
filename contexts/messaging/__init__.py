"""Messaging bounded context (D129).

The Phase 2-A Wave 1 communication substrate — per-tenant
persistence of the Message aggregate and outbound delivery through a
vendor-agnostic MessageDeliveryPort. Messaging is the channel
through which all three product modes (attentional, workflow,
observation-and-suggestion) reach the user. Hexagonal layers
within: ``domain`` / ``ports`` / ``application`` / ``adapters``.

D119 commits the channel and vendor (WhatsApp via the Twilio
Sandbox for WhatsApp); D129 commits this bounded-context substrate.
"""
