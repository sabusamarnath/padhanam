from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from vadakkan.config.base import MeridianSettings
from vadakkan.config.profiles import Profile, get_profile


class TLSMode(StrEnum):
    PLAINTEXT = "plaintext"
    TLS = "tls"
    MTLS = "mtls"


class InferenceSettings(MeridianSettings):
    """LiteLLM gateway and model configuration.

    The endpoint, default model, and master key are the values used by
    Meridian application code (when it lands in S7) and by the smoke-test
    Make targets in S6. The master key has no default: it is a real
    secret and must be supplied via .env, which surfaces a missing
    configuration as a Pydantic validation error rather than a silent
    fall-through.
    """

    litellm_endpoint: str = "http://litellm:4000"
    litellm_master_key: str
    default_model: str = "qwen2.5:7b"
    tls_mode: TLSMode = TLSMode.PLAINTEXT

    @model_validator(mode="after")
    def enforce_prod_tls(self) -> "InferenceSettings":
        # D20: prod profile has no plaintext escape hatch.
        if get_profile() is Profile.PROD and self.tls_mode is TLSMode.PLAINTEXT:
            raise ValueError(
                "InferenceSettings.tls_mode=plaintext is not permitted under "
                "MERIDIAN_PROFILE=prod (D20)."
            )
        return self
