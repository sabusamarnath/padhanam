from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from platform.config.base import MeridianSettings
from platform.config.profiles import Profile, get_profile


class TLSMode(StrEnum):
    PLAINTEXT = "plaintext"
    TLS = "tls"
    MTLS = "mtls"


class InferenceSettings(MeridianSettings):
    """LiteLLM gateway and model configuration.

    Lands real values in S6 when LiteLLM and Ollama enter Compose. Defaults
    here are dev-shaped so the smoke test can instantiate without an .env.
    """

    litellm_endpoint: str = "http://litellm:4000"
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
