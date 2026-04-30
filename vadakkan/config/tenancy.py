from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from vadakkan.config.base import VadakkanSettings


class ControlPlaneSettings(VadakkanSettings):
    """Connection details for the dedicated control-plane Postgres instance.

    The control plane hosts the tenant registry and any other operator-owned,
    jurisdiction-spanning data per D33. It is a single instance, never shared
    with a tenant data plane. The S10 registry adapter reads these values to
    open a connection; from S10 onward, registry rows are the source of truth
    for per-tenant connection details (which arrive encrypted per D21).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
        env_prefix="POSTGRES_CONTROL_PLANE_",
    )

    user: str
    password: str
    db: str
    host: str = "postgres-control-plane"
    port: int = 5432


class TenantPostgresSettings(VadakkanSettings):
    """Connection details for a per-tenant Postgres instance.

    Instantiate via ``TenantPostgresSettings.for_tenant(tenant_label)`` which
    binds the env-var prefix to ``POSTGRES_TENANT_<LABEL>_``. P3 ships two
    tenant labels, ``a`` and ``b``, per D32. The S10 registry adapter reads
    these values to bootstrap the registry rows for the test set; live
    per-tenant connections from S11 onward flow through registry decryption
    (D21) rather than directly through these settings, so ``for_tenant`` is
    a bootstrap surface, not a routing primitive.

    Tenant labels beyond ``a``/``b`` require both a new Compose service
    (per D32, instance creation deferred) and matching env vars; adding a
    label here without the Compose-side instance produces a Pydantic
    validation error at instantiation, which is the desired failure mode.
    """

    user: str
    password: str
    db: str
    host: str = ""
    port: int = 5432

    @classmethod
    def for_tenant(cls, tenant_label: str) -> "TenantPostgresSettings":
        label = tenant_label.lower()
        prefix = f"POSTGRES_TENANT_{label.upper()}_"
        default_host = f"postgres-tenant-{label}"
        merged = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            env_nested_delimiter="__",
            extra="ignore",
            case_sensitive=False,
            env_prefix=prefix,
        )
        bound = type(
            f"_TenantPostgresSettings_{label}",
            (cls,),
            {"model_config": merged},
        )
        instance = bound()
        if not instance.host:
            instance.host = default_host
        return instance
