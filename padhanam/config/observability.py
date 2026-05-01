from __future__ import annotations

import base64
from pathlib import Path

from pydantic import Field

from padhanam.config.base import PadhanamSettings


class ObservabilitySettings(PadhanamSettings):
    """Trace store and security-event configuration.

    Langfuse keys are read from the LANGFUSE_INIT_PROJECT_* env vars that
    Langfuse 3 already consumes for headless org/project bootstrap (see
    S4) via Pydantic validation aliases — adding a parallel set of
    LANGFUSE_* vars would store the same secret twice. The OTLP endpoint
    defaults to the self-hosted Langfuse 3 ingestion path on the
    Compose-internal network (D27, D20 dev plaintext); production points
    this at the regional Langfuse stack via .env override. The OTLP
    basic-auth header is derived from the keys; LiteLLM consumes the
    derived header through OTEL_HEADERS at container startup.
    """

    langfuse_public_key: str = Field(
        default="pk-lf-dev-not-set",
        validation_alias="LANGFUSE_INIT_PROJECT_PUBLIC_KEY",
    )
    langfuse_secret_key: str = Field(
        default="sk-lf-dev-not-set",
        validation_alias="LANGFUSE_INIT_PROJECT_SECRET_KEY",
    )
    langfuse_project_id: str = Field(
        default="padhanam-dev",
        validation_alias="LANGFUSE_INIT_PROJECT_ID",
    )
    langfuse_host: str = "https://langfuse.localhost"
    otlp_endpoint: str = (
        "http://langfuse-web:3000/api/public/otel/v1/traces"
    )
    security_log_path: Path = Path("logs/security.jsonl")

    @property
    def otlp_basic_auth_header(self) -> str:
        """Authorization header value for Langfuse OTLP ingestion.

        Langfuse 3 expects HTTP Basic auth with base64-encoded
        ``public_key:secret_key``. The padding ``=`` characters that may
        appear in the base64 output are not URL-encoded — the OTel SDK
        splits OTEL_HEADERS pairs on the first ``=`` only, so trailing
        padding is preserved as part of the value.
        """
        token = f"{self.langfuse_public_key}:{self.langfuse_secret_key}"
        b64 = base64.b64encode(token.encode("utf-8")).decode("ascii")
        return f"Basic {b64}"

    @property
    def otel_headers_env_value(self) -> str:
        """Value for the OTEL_HEADERS env var consumed by LiteLLM.

        LiteLLM's ``_get_headers_dictionary`` parses the env var by
        splitting on ``,`` (between headers) and ``=`` once (between key
        and value), and does *not* URL-decode the value before passing it
        to the OTLP exporter. So the literal HTTP header value goes here
        without any percent-encoding — the space between ``Basic`` and
        the base64 is preserved verbatim and reaches Langfuse as a
        well-formed Authorization header.
        """
        return f"Authorization={self.otlp_basic_auth_header}"
