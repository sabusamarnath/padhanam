from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from padhanam.config.base import PadhanamSettings


class MessagingAdapter(StrEnum):
    """The outbound message delivery adapter selected at composition root."""

    LOCAL_ECHO = "local_echo"
    TWILIO = "twilio"


class MessagingSettings(PadhanamSettings):
    """Messaging channel and delivery-adapter configuration (D119, D129).

    ``messaging_adapter`` selects the outbound delivery adapter at the
    composition root — ``local_echo`` (the default: local-first
    development, no vendor credentials) or ``twilio`` (WhatsApp via the
    Twilio Sandbox). The Twilio fields carry empty-string defaults so
    local development runs without them; selecting the twilio adapter
    without credentials surfaces a clear validation error here rather
    than a silent fall-through at send time.

    Environment variables (case-insensitive): ``MESSAGING_ADAPTER``,
    ``TWILIO_ACCOUNT_SID``, ``TWILIO_AUTH_TOKEN``,
    ``TWILIO_WHATSAPP_FROM``, ``WEBHOOK_TENANT_ID``,
    ``WEBHOOK_JURISDICTION``, ``WEBHOOK_URL``. The production swap to
    the Twilio adapter is configuration, not a code change, per the
    local-first principle.

    The ``webhook_*`` fields configure the inbound webhook receiver.
    Twilio webhooks carry no Padhanam Principal, so the receiver
    synthesises an operator ActorContext for a single configured
    tenant (Phase 2-A is single-tenant operator dogfooding; multi-tenant
    webhook routing is the deferred multi-channel-UX work).
    """

    messaging_adapter: MessagingAdapter = MessagingAdapter.LOCAL_ECHO
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    # The platform's WhatsApp sender. Defaults to Twilio's shared
    # Sandbox-for-WhatsApp number; a bare E.164 number, the Twilio
    # adapter applies the ``whatsapp:`` prefix.
    twilio_whatsapp_from: str = "+14155238886"
    # Inbound-webhook configuration. ``webhook_tenant_id`` is the
    # registered tenant inbound WhatsApp messages route to;
    # ``webhook_jurisdiction`` is stamped on the synthesised
    # TenantContext; ``webhook_url`` is the public URL Twilio is
    # configured to call (used for X-Twilio-Signature verification —
    # empty falls back to the request URL the route observes).
    webhook_tenant_id: str = ""
    webhook_jurisdiction: str = "eu-west"
    webhook_url: str = ""
    # D134 confidence-aware composition cut-offs. Case 1 (proceed)
    # fires at confidence >= ``confidence_high_cutoff``; Case 2
    # (shape-aware clarification with PendingClarification) fires at
    # confidence in ``[confidence_medium_cutoff, confidence_high_cutoff)``;
    # Case 3 (generic clarification) fires below. Phase 2-A operates
    # one operation class (intake-canonical portfolio writes per D128)
    # with one cut-off pair; the per-operation-class configuration
    # surface activates at Phase 2-B+ when higher-stakes operations
    # land. Tunable as dogfooding calibration data accumulates.
    confidence_high_cutoff: float = 0.8
    confidence_medium_cutoff: float = 0.5

    @model_validator(mode="after")
    def require_confidence_cutoffs_ordered(self) -> "MessagingSettings":
        if not 0.0 <= self.confidence_medium_cutoff <= self.confidence_high_cutoff <= 1.0:
            raise ValueError(
                "confidence cut-offs must satisfy "
                "0.0 <= medium <= high <= 1.0"
            )
        return self

    @model_validator(mode="after")
    def require_twilio_credentials(self) -> "MessagingSettings":
        # The twilio adapter cannot function without credentials; fail
        # loudly at configuration time rather than at first send.
        if self.messaging_adapter is MessagingAdapter.TWILIO:
            missing = [
                name
                for name in (
                    "twilio_account_sid",
                    "twilio_auth_token",
                    "twilio_whatsapp_from",
                )
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    "MESSAGING_ADAPTER=twilio requires the Twilio "
                    f"credentials {missing}"
                )
        return self


__all__ = ["MessagingAdapter", "MessagingSettings"]
