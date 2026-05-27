"""CitedResponse Protocol conformance scenario (D138, S51).

For every registered ConversationFlow implementer, verify the
implementer's response value object satisfies the CitedResponse Protocol
via isinstance check at runtime. The CitedResponse Protocol at
``shared_kernel/conversation_flow.py`` commits the three citation tuple
fields (cited_intake_records, cited_audit_events, cited_artefacts);
each implementer's response shape must carry all three for the
``@runtime_checkable`` Protocol's isinstance check to pass.

The scenario walks the cell through an open + turn lifecycle, extracts
the response value object from ``ConversationState.payload`` under the
implementer-specific key, and runs ``isinstance(response, CitedResponse)``.
The key names vary per implementer (manual entry: ``cell_response``;
audit-conversation: ``audit_response``); the scenario knows about both
via a small lookup table — adding a future implementer adds an entry.

Per S49 structural-test SSOT binding: the D138 architectural commitment
admits this structural test; the test lands at the commitment's commit
(S51 commit 1 commits the charter; S51 commit 5 commits the structural
test).
"""

from __future__ import annotations

import asyncio

from shared_kernel.conversation_flow import CitedResponse

from tests.contract.conversation_flow.conftest import (
    ConversationFlowImplementerFixture,
)


# Payload key per implementer where the response value object lands.
# Adding a future implementer adds an entry here.
_PAYLOAD_KEY_PER_IMPLEMENTER: dict[str, str] = {
    "manual_entry_cell": "cell_response",
    "audit_conversation_cell": "audit_response",
    "mirror_conversation_cell": "mirror_response",
}


def test_response_satisfies_cited_response_protocol(
    conversation_flow_implementer: ConversationFlowImplementerFixture,
) -> None:
    """Every implementer's response value object satisfies CitedResponse.

    Runs against every registered implementer. The implementer must be
    listed in ``_PAYLOAD_KEY_PER_IMPLEMENTER`` (a new implementer's
    registration module is the seam to extend this map).
    """
    name = conversation_flow_implementer.name
    assert name in _PAYLOAD_KEY_PER_IMPLEMENTER, (
        f"Implementer {name!r} missing from _PAYLOAD_KEY_PER_IMPLEMENTER. "
        "Add the payload-key entry when registering a new implementer."
    )
    payload_key = _PAYLOAD_KEY_PER_IMPLEMENTER[name]

    instance = conversation_flow_implementer.make_instance()

    async def _drive() -> object:
        opened = await instance.open(
            conversation_flow_implementer.sample_invocation
        )
        turned = await instance.turn(
            opened, conversation_flow_implementer.sample_input
        )
        return turned.payload.get(payload_key)

    response = asyncio.run(_drive())
    assert response is not None, (
        f"Expected payload['{payload_key}'] to carry the response value "
        f"object for implementer {name!r}, found None."
    )
    assert isinstance(response, CitedResponse), (
        f"Implementer {name!r}'s response value object does not satisfy "
        "the CitedResponse Protocol; missing one of "
        "cited_intake_records, cited_audit_events, cited_artefacts."
    )
