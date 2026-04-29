"""Compute env-var values derived from vadakkan/config/ and emit them in
.env-file format on stdout.

The ``derive-env`` Make target redirects stdout into ``.env.derived``;
docker compose loads ``.env`` and ``.env.derived`` together via
``--env-file`` flags. Storing the LiteLLM OTLP basic-auth header here
rather than in the operator-edited ``.env`` keeps a single source of
truth for the Langfuse keys: rotating them is a single ``.env`` edit
followed by a fresh ``make up`` (which re-derives). D19's "secrets
enter through vadakkan/config/" rule is satisfied because this script
imports ObservabilitySettings to compute the value, rather than reading
.env directly.
"""

from __future__ import annotations

from vadakkan.config import ObservabilitySettings


def main() -> None:
    obs = ObservabilitySettings()
    print(f"LITELLM_OTEL_HEADERS={obs.otel_headers_env_value}")


if __name__ == "__main__":
    main()
