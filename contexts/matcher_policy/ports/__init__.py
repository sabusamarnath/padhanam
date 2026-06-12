"""matcher_policy ports — the seam's two sides (D186, D17).

``MatcherPolicyRepository`` (write) is what optimization calls on apply;
``MatcherPolicyReader`` (read) is what the matcher reads on run.
"""

from __future__ import annotations

from contexts.matcher_policy.ports.matcher_policy_reader import (
    MatcherPolicyReader,
)
from contexts.matcher_policy.ports.matcher_policy_repository import (
    MatcherPolicyRepository,
)

__all__ = ["MatcherPolicyReader", "MatcherPolicyRepository"]
