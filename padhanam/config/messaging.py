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
    ``TWILIO_WHATSAPP_FROM``. The production swap to the Twilio adapter
    is configuration, not a code change, per the local-first principle.
    """

    messaging_adapter: MessagingAdapter = MessagingAdapter.LOCAL_ECHO
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    # The platform's WhatsApp sender — the Twilio Sandbox number at
    # Phase 2-A. A bare E.164 number; the Twilio adapter applies the
    # ``whatsapp:`` prefix.
    twilio_whatsapp_from: str = ""

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
