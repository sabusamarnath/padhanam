"""S103u/D222: the pure contact domain — normalized company match, usability, the
derived warm access, the override, and the contact-specific warming action."""

from __future__ import annotations

from uuid import uuid4

from contexts.daily_driver.domain.contacts import (
    ContactView,
    contacts_for_company,
    derive_warm,
    effective_warm,
    is_usable,
    lead_company,
    normalize_company,
    warming_action,
)


def _c(name, company, *, degree=None, strength=None, reachability=None,
       provenance="user_authored"):
    return ContactView(
        contact_id=uuid4(), name=name, email=f"{name}@x.com".lower(),
        company=company, degree=degree, strength=strength,
        reachability=reachability, capture_source="email",
        provenance_origin=provenance,
    )


def test_normalize_and_lead_company():
    assert normalize_company("  Acme ") == "acme"
    assert normalize_company(None) == ""
    assert lead_company("Acme — VP Product") == "Acme"
    assert lead_company("Acme") == "Acme"


def test_company_match_is_normalized():
    contacts = (_c("Jane", "Acme"), _c("Bob", "globex-legal"))
    assert len(contacts_for_company("  acme ", contacts)) == 1
    assert contacts_for_company("Unknown", contacts) == ()
    assert contacts_for_company("", contacts) == ()  # no company, no match


def test_is_usable_requires_proofed_strength_or_reachability():
    assert is_usable(_c("A", "X", strength="close"))
    assert is_usable(_c("A", "X", strength="medium"))
    assert is_usable(_c("A", "X", reachability="easy"))
    # unproofed (all None) is NOT usable — the operator must author it (D200)
    assert not is_usable(_c("A", "X"))
    # weak + hard offers no path
    assert not is_usable(_c("A", "X", strength="weak", reachability="hard"))


def test_derive_warm_from_a_usable_contact():
    warm = (_c("Jane", "Acme", strength="close"),)
    assert derive_warm("Acme", warm) == "warm"
    # an unproofed contact at the company does not make it warm yet
    unproofed = (_c("Bob", "Acme"),)
    assert derive_warm("Acme", unproofed) == "cold"
    assert derive_warm("Acme", ()) == "cold"


def test_effective_warm_override_beats_derived():
    contacts = ()  # derives cold
    assert effective_warm("warm", "Acme", contacts) == "warm"   # override wins
    assert effective_warm("cold", "Acme", (_c("J", "Acme", strength="close"),)) == "cold"
    # no override -> the derived value shows through
    assert effective_warm(None, "Acme", (_c("J", "Acme", strength="close"),)) == "warm"
    assert effective_warm(None, "Acme", ()) == "cold"


def test_warming_action_names_the_real_contact():
    close_first = (_c("Jane", "Acme", degree="first", strength="close"),)
    assert "Jane" in warming_action("Acme", close_first)
    assert "referral" in warming_action("Acme", close_first).lower()
    second = (_c("Yuki", "Acme", degree="second", strength="medium"),)
    assert "intro" in warming_action("Acme", second).lower()
    # unproofed contact at company -> nudge to proof
    unproofed = (_c("Bob", "Acme"),)
    assert "proof" in warming_action("Acme", unproofed).lower()
    # no contact -> nudge to add
    assert "add" in warming_action("Acme", ()).lower()


def test_warming_action_prefers_first_degree_close():
    contacts = (
        _c("Weak", "Acme", degree="second", strength="weak", reachability="easy"),
        _c("Strong", "Acme", degree="first", strength="close"),
    )
    assert "Strong" in warming_action("Acme", contacts)
