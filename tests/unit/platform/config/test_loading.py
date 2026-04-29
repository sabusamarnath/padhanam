from __future__ import annotations

import pytest

from platform.config import (
    InferenceSettings,
    ObservabilitySettings,
    Profile,
    SecuritySettings,
    get_profile,
)
from platform.config.inference import TLSMode


def test_profile_defaults_to_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MERIDIAN_PROFILE", raising=False)
    assert get_profile() is Profile.DEV


def test_inference_settings_load_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MERIDIAN_PROFILE", raising=False)
    settings = InferenceSettings()
    assert settings.litellm_endpoint.startswith("http://")
    assert settings.default_model == "qwen2.5:7b"
    assert settings.tls_mode is TLSMode.PLAINTEXT


def test_inference_settings_env_var_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MERIDIAN_PROFILE", raising=False)
    monkeypatch.setenv("DEFAULT_MODEL", "llama3.1:8b")
    settings = InferenceSettings()
    assert settings.default_model == "llama3.1:8b"


def test_inference_settings_reject_plaintext_in_prod(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MERIDIAN_PROFILE", "prod")
    monkeypatch.setenv("TLS_MODE", "plaintext")
    with pytest.raises(ValueError, match="plaintext.*not permitted.*prod"):
        InferenceSettings()


def test_observability_settings_load_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MERIDIAN_PROFILE", raising=False)
    settings = ObservabilitySettings()
    assert settings.langfuse_host.startswith("https://")
    assert settings.security_log_path.name == "security.jsonl"


def test_security_settings_kek_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MERIDIAN_PROFILE", raising=False)
    settings = SecuritySettings()
    raw = bytes.fromhex(settings.kek_hex)
    assert len(raw) == 32


def test_security_settings_reject_short_kek(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MERIDIAN_PROFILE", raising=False)
    monkeypatch.setenv("KEK_HEX", "deadbeef")
    with pytest.raises(ValueError, match="32 bytes"):
        SecuritySettings()
