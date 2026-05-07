from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from padhanam.config.base import PadhanamSettings


class Neo4jSettings(PadhanamSettings):
    """Connection details for the shared Neo4j instance per D63.

    Phase 1 ships a single shared instance (``padhanam-neo4j`` Compose
    service); per-tenant isolation is enforced at the property level,
    structurally gated by the ``TenantScopedNeo4jSession`` wrapper at
    ``contexts/ingestion/adapters/outbound/neo4j/``. Production
    deployment context may revisit per the deferred-decisions entry.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
        env_prefix="NEO4J_",
    )

    user: str
    password: str
    host: str = "padhanam-neo4j"
    bolt_port: int = 7687

    @property
    def bolt_uri(self) -> str:
        return f"bolt://{self.host}:{self.bolt_port}"
