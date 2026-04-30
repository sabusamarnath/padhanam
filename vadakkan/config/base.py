from __future__ import annotations

from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from vadakkan.config.profiles import Profile, get_profile


class SecretManagerSource(PydanticBaseSettingsSource):
    """Production secret-manager-backed source.

    Vendor selection (AWS Secrets Manager, GCP Secret Manager, Vault, etc.) is
    deferred until production deployment context exists. The interface is
    fixed now so the production swap is configuration, not refactor (D19, D21).
    """

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        # Stubbed: returns "no value" so env_settings still wins for resolution.
        # Production deployment replaces this class with a real implementation
        # bound to the chosen secret manager.
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        # Same posture as get_field_value: an empty mapping lets env_settings
        # remain the resolver until the production binding lands. The
        # placeholder is intentional — production will not ship until this
        # class is replaced (D19, D21).
        return {}


class VadakkanSettings(BaseSettings):
    """Base for every Vadakkan Settings class.

    Every secret and environment-derived value enters the application through
    a subclass of this type. No other module reads .env or calls os.getenv
    (D19, enforced by import-linter).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Source priority: init args > env vars > .env > file secrets.
        # Production prepends SecretManagerSource ahead of env so resolved
        # secrets win over any leaked env-var fallback.
        if get_profile() is Profile.PROD:
            return (
                init_settings,
                SecretManagerSource(settings_cls),
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
