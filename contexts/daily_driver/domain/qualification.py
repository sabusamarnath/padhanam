"""The stage-aware qualification model — the MEDDPICC equivalent for a job search
(S103w, D228). Pure (D16, stdlib only).

Eight job-search-native fields, each a value plus a ``last_touched`` timestamp,
stored as dynamic-key schemaless props on ``:Opportunity`` (``q_<key>`` /
``q_<key>_ts``). An authored stage-activation map assigns each field the stage(s)
where it carries weight; activation is **soft** (all fields always visible, the
active ones highlighted, the rest dimmed). Champion and hiring-decision-maker read
from the role-typed contacts at the opportunity's company (D227) when not overridden
by a stored value. Freshness (D229) is layered on ``last_touched`` in the read use
case, gated by this activation map.
"""

from __future__ import annotations

from dataclasses import dataclass

# The eight fields (key, human label). Native names, MEDDPICC equivalent in comments.
QUAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("role_open", "Why the role is open"),                 # pain
    ("success_measures", "Role success measures"),          # metrics
    ("selection_criteria", "Selection criteria"),           # decision criteria
    ("interview_process", "Interview process"),             # decision process
    ("champion", "Champion"),                               # champion (from D227)
    ("decision_maker", "Hiring decision-maker"),            # economic buyer (D227)
    ("competing_candidates", "Competing candidates"),       # competition
    ("vetting_checks", "Vetting & checks"),                 # paperwork
)
QUAL_FIELD_KEYS: frozenset[str] = frozenset(k for k, _ in QUAL_FIELDS)

# The people fields populated from contact process-roles (D227) when not overridden.
_ROLE_FIELDS = {"champion": "champion", "decision_maker": "decision_maker"}

# The stage-activation map (D228) — a domain-level default this session
# (operator-tunable/stored is deferred). Each field carries weight at its stage(s).
ACTIVATION: dict[str, frozenset[str]] = {
    "Lead": frozenset({"role_open", "success_measures"}),
    "Application": frozenset({"selection_criteria"}),
    "Screening": frozenset({"champion", "decision_maker"}),
    "Interviewing": frozenset({"interview_process"}),
    "Offer": frozenset({"competing_candidates", "vetting_checks"}),
}


def field_active_at_stage(field_key: str, stage: str) -> bool:
    """Whether a field carries weight at ``stage`` per the activation map (D228)."""
    return field_key in ACTIVATION.get(stage, frozenset())


@dataclass(frozen=True)
class QualificationField:
    """One qualification field as read for the surface (D228). ``last_touched`` is
    the ISO string from ``q_<key>_ts`` (or None); ``active`` is stage-activation;
    ``from_contact`` marks a people field whose value came from a role-typed contact;
    ``risk`` is the stage-relative freshness verdict (D229), filled by the read."""

    key: str
    label: str
    value: str | None
    last_touched: str | None
    active: bool
    from_contact: bool = False
    risk: str | None = None   # None / "stale" (surfaced only when active, D229)
    draft: str | None = None  # a JD-extracted suggestion (S103ad/D236); never the value


def qualification_value(qual_props: dict, key: str) -> str | None:
    return qual_props.get(f"q_{key}") or None


def qualification_ts(qual_props: dict, key: str) -> str | None:
    return qual_props.get(f"q_{key}_ts") or None


def qualification_draft(qual_props: dict, key: str) -> str | None:
    """The JD-extracted draft suggestion for a field (``q_<key>_draft``, D236)."""
    return qual_props.get(f"q_{key}_draft") or None


def build_qualification_base(
    *, qual_props: dict, stage: str, role_by_field: dict[str, str] | None = None
) -> tuple[QualificationField, ...]:
    """The eight fields with values (people fields falling back to the role-typed
    contact) + stage activation, WITHOUT freshness (the read use case layers D229's
    stage-relative risk on top). ``role_by_field`` maps ``champion`` /
    ``decision_maker`` to a contact name at the opportunity's company (D227)."""
    role_by_field = role_by_field or {}
    out: list[QualificationField] = []
    for key, label in QUAL_FIELDS:
        value = qualification_value(qual_props, key)
        from_contact = False
        if value is None and key in _ROLE_FIELDS and role_by_field.get(key):
            value = role_by_field[key]
            from_contact = True
        out.append(QualificationField(
            key=key, label=label, value=value,
            last_touched=qualification_ts(qual_props, key),
            active=field_active_at_stage(key, stage), from_contact=from_contact,
            draft=qualification_draft(qual_props, key),
        ))
    return tuple(out)


__all__ = [
    "ACTIVATION", "QUAL_FIELDS", "QUAL_FIELD_KEYS", "QualificationField",
    "build_qualification_base", "field_active_at_stage", "qualification_draft",
    "qualification_ts", "qualification_value",
]
