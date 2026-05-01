from __future__ import annotations

import os
from enum import StrEnum


class Profile(StrEnum):
    DEV = "dev"
    PROD = "prod"


def get_profile() -> Profile:
    """Resolve the active deployment profile from PADHANAM_PROFILE.

    This is the only sanctioned os.getenv call in the codebase (see D19);
    every other module reads through platform/config/ Settings classes.
    """
    raw = os.getenv("PADHANAM_PROFILE", "dev").strip().lower()
    return Profile(raw)
