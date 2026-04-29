from __future__ import annotations

from pathlib import Path

from platform.config.base import MeridianSettings


class ObservabilitySettings(MeridianSettings):
    """Trace store and security-event configuration.

    Langfuse keys land for real in S6 when LiteLLM emits its first trace; the
    OTel collector endpoint lands in S7. Security log path is live now (D26).
    """

    langfuse_public_key: str = "pk-lf-dev-not-set"
    langfuse_secret_key: str = "sk-lf-dev-not-set"
    langfuse_host: str = "https://langfuse.localhost"
    otel_collector_endpoint: str = "http://otel-collector:4318"
    security_log_path: Path = Path("logs/security.jsonl")
