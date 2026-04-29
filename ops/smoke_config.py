"""Resolve smoke-test configuration through vadakkan/config/ and emit it
in shell-export form on stdout.

The make smoke-llm target consumes this with ``eval "$(...)"`` so the
target invokes ``uv run`` exactly once per smoke (cold-start cost shows
up in the smoke total). Keeping the resolver here rather than inlined
in the Makefile keeps the D19 boundary clean and lets the smoke target
stay readable.
"""

from __future__ import annotations

from vadakkan.config import InferenceSettings, ObservabilitySettings


def main() -> None:
    inference = InferenceSettings()
    observability = ObservabilitySettings()
    print(f"SMOKE_KEY={inference.litellm_master_key}")
    print(f"SMOKE_MODEL={inference.default_model}")
    verify_url = (
        f"{observability.langfuse_host}"
        f"/project/{observability.langfuse_project_id}/traces"
    )
    print(f"SMOKE_VERIFY_URL={verify_url}")


if __name__ == "__main__":
    main()
