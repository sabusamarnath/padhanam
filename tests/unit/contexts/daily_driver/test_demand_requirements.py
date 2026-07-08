"""Demand-requirements domain: config-driven schema, content-hash ids, idempotent
merge, and the pure proof transforms (S103ah, D240)."""

from __future__ import annotations

from contexts.daily_driver.domain import demand_requirements as dr


def _draft(text, importance="essential"):
    return dr.make_requirement(text=text, importance=importance, proof_state=dr.PROOF_DRAFT)


def test_config_driven_item_schema_is_built_from_requirement_fields() -> None:
    schema = dr.requirement_item_schema()
    # the schema's properties are exactly the config table's keys — adding a
    # REQUIREMENT_FIELDS row would extend it with no code change
    assert set(schema["properties"]) == {k for k, *_ in dr.REQUIREMENT_FIELDS}
    assert schema["properties"]["importance"]["enum"] == list(dr.IMPORTANCE_LEVELS)
    assert schema["additionalProperties"] is False


def test_importance_coercion_defaults_to_essential() -> None:
    assert dr.coerce_importance("preferred") == "preferred"
    assert dr.coerce_importance("NICE_TO_HAVE") == "nice_to_have"
    assert dr.coerce_importance("desirable") == "essential"   # unknown → the must default
    assert dr.coerce_importance(None) == "essential"


def test_id_is_stable_content_hash_dedup_by_text() -> None:
    a = _draft("Deep technical expertise")
    b = _draft("  deep   TECHNICAL  expertise ")  # same normalized text
    assert a["id"] == b["id"]
    assert _draft("Something else")["id"] != a["id"]


def test_parse_extracted_is_discrete_deduped_and_capped() -> None:
    raw = [{"text": f"req {i}", "importance": "essential"} for i in range(dr.MAX_REQUIREMENTS + 5)]
    raw += [{"text": "req 0", "importance": "preferred"}]  # duplicate of the first
    items = dr.parse_extracted(raw)
    assert len(items) == dr.MAX_REQUIREMENTS       # capped
    assert all(r["proof_state"] == "draft" for r in items)


def test_merge_keeps_confirmed_and_is_idempotent() -> None:
    base = (_draft("Python"), _draft("Kafka"))
    confirmed = dr.confirm(base, base[0]["id"])          # confirm Python
    fresh = (_draft("Python"), _draft("Kafka"))           # re-extraction, same set
    merged = dr.merge_extracted(confirmed, fresh)
    assert len(merged) == 2                               # no duplicate
    py = [r for r in merged if r["text"] == "Python"][0]
    assert py["proof_state"] == "confirmed"               # invariant 4 — not clobbered
    # idempotent: merging again is a fixed point
    assert dr.merge_extracted(merged, fresh) == merged


def test_serialize_deserialize_round_trip_preserves_proof_state() -> None:
    items = dr.confirm((_draft("A"), _draft("B", "preferred")), _draft("A")["id"])
    assert dr.deserialize(dr.serialize(items)) == items
    assert dr.deserialize(None) == ()
    assert dr.deserialize("not json") == ()


def test_confirm_dismiss_edit_add_transforms() -> None:
    items = (_draft("A"), _draft("B"))
    a_id = items[0]["id"]
    # confirm
    assert dr.confirm(items, a_id)[0]["proof_state"] == "confirmed"
    # dismiss
    assert [r["text"] for r in dr.dismiss(items, a_id)] == ["B"]
    # edit → confirmed, id re-derives from new text, order preserved
    edited = dr.edit(items, a_id, text="A improved", importance="preferred")
    assert edited[0]["text"] == "A improved"
    assert edited[0]["importance"] == "preferred"
    assert edited[0]["proof_state"] == "confirmed"
    assert [r["text"] for r in edited] == ["A improved", "B"]
    # add (confirmed); adding a duplicate confirms the existing item instead of a dup
    added = dr.add(items, text="C", importance="nice_to_have")
    assert [r["text"] for r in added] == ["A", "B", "C"]
    dup = dr.add(items, text="A", importance="essential")
    assert len(dup) == 2 and dup[0]["proof_state"] == "confirmed"
    # unknown ids / empty text are no-ops
    assert dr.confirm(items, "nope") == items
    assert dr.edit(items, "nope", text="x", importance="essential") == items
    assert dr.add(items, text="  ", importance="essential") == items


def test_confirmed_texts_is_the_match_criteria() -> None:
    items = (_draft("A"), _draft("B"), _draft("C"))
    items = dr.confirm(items, items[0]["id"])
    items = dr.confirm(items, items[2]["id"])
    assert dr.confirmed_texts(items) == ("A", "C")   # only confirmed feed the match
