"""Static guards on the daily-driver /app surface markup (S84, design-language §2).

The action-Today render is HTML/JS served statically; these tests read the file
and assert the S84 legibility cleanup holds — the legend and the per-row reorder
chevrons are gone, the proposed order still renders, and the row carries no
domain/tier word in the meta (tint + icon carry tier + category). Regression
guards, not a DOM harness; browser-interactive confirmation is the operator's.
"""

from __future__ import annotations

from pathlib import Path

_HTML = (
    Path(__file__).resolve().parents[4]
    / "apps" / "api" / "static" / "daily_driver.html"
).read_text()


def test_no_legend_element_or_swatch():
    # AC1: the work/personal surface legend is removed (tint carries tier).
    assert 'class="legend"' not in _HTML
    assert 'class="swatch' not in _HTML


def test_no_per_row_reorder_chevrons():
    # AC2: the ▲▼ per-row reorder affordance is removed (the full §5 override
    # is post-week); only the system's proposed order renders.
    assert "data-up=" not in _HTML
    assert "data-down=" not in _HTML
    assert 'class="reorder"' not in _HTML


def test_proposed_order_still_renders():
    # AC2: the read's items still render in their proposed order.
    assert "render(data.items)" in _HTML
    assert "items.forEach" in _HTML


def test_action_today_meta_is_bare_no_domain_word():
    # AC4: the meta line carries only the read's bare detail — no domain/tier
    # word composed in the render (tint = tier, icon = category).
    assert 'class="meta">${escapeHtml(it.detail)}' in _HTML


_ROUTER = (
    Path(__file__).resolve().parents[4]
    / "apps" / "api" / "routers" / "daily_driver.py"
).read_text()


def test_today_endpoints_untouched_server_side():
    # AC6: render-only — the server's /today read and the /today/order endpoint
    # are unchanged (only the client reorder affordance was removed).
    assert '@router.get("/today"' in _ROUTER
    assert '"/today/order"' in _ROUTER


# --- S85 (D181): recommendation-shaped action Today -------------------------


def test_action_today_leads_with_needs_you_collapses_the_rest():
    # The head set is {needs-you, behind} (no at-risk status exists); the render
    # leads with them in full and collapses the quiet into a summary.
    assert 'new Set(["NEEDS_YOU", "BEHIND"])' in _HTML
    assert "function collapsibleSummary(" in _HTML
    assert "on track" in _HTML       # the "N on track" quiet summary
    assert "done earlier" in _HTML    # the "N done earlier" summary


def test_collapse_is_default_state_filled_on_toggle():
    # No display:none streaming: the summary is the default (collapsed) and its
    # rows are appended only on an explicit expand toggle.
    assert "collapse-body" in _HTML
    assert 'body.style.display = "none"' in _HTML
    assert "body.appendChild(rowEl(it))" in _HTML


def test_done_history_collapsed_not_flat():
    # The done-earlier section is one collapsed summary, not a flat row loop.
    assert "history.forEach" not in _HTML
    assert "} done earlier`" in _HTML


# --- S86 (D182): one lens per view (Today list-only; dash holds the moat) ----


def _today_template() -> str:
    start = _HTML.index('if (activeView === "today")')
    end = _HTML.index('else if (activeView === "dash")', start)
    return _HTML[start:end]


def _dash_template() -> str:
    start = _HTML.index('else if (activeView === "dash")')
    end = _HTML.index('else if (activeView === "coverage")', start)
    return _HTML[start:end]


def _coverage_template() -> str:
    start = _HTML.index('else if (activeView === "coverage")')
    end = _HTML.index("} else {", start)
    return _HTML[start:end]


def test_today_renders_list_and_history_only():
    today = _today_template()
    assert 'id="list"' in today
    assert 'id="history-section"' in today
    for cut in ('id="goals"', 'id="tasks"', 'id="moat"', 'id="suggestions"'):
        assert cut not in today, f"{cut} must not render on Today (D182)"


def test_dash_view_live_and_holds_moat_with_in_goal_suggestions():
    # D190/S94: suggestions ride the goal (the suggest-block in the expand),
    # so the dash holds only the moat — the global suggestions section and its
    # loader were removed.
    assert '{ id: "dash", label: "How am I doing", live: true }' in _HTML
    dash = _dash_template()
    assert 'id="moat"' in dash
    assert 'id="suggestions"' not in dash
    assert "loadAssess()" in dash  # D199/S101: the toggle-aware fetch+dispatch
    assert "function loadSuggestions" not in _HTML


def test_dash_view_carries_the_list_map_toggle_over_one_source():
    # D199/S101: the assess surface gains a List/Map toggle; both renderings read
    # the cached units-by-goal source (assessData), with no second data path.
    dash = _dash_template()
    assert 'id="assess-toggle"' in dash
    assert 'data-mode="list"' in dash and 'data-mode="map"' in dash
    assert "renderAssess()" in dash  # re-render from cache on toggle — no refetch
    assert "let assessMode" in _HTML and "assessData = await api" in _HTML
    for fn in ("function renderAssessList", "function renderAssessMap",
               "function mapNodeEl", "function buildMapFeeders",
               "function measurableOutcome"):
        assert fn in _HTML, fn


def test_map_renders_levers_and_work_as_siblings_not_unit_under_lever():
    # The decisive Step-0 invariant in the render: serving work feeds the outcome
    # as a sibling of the levers (the graph links work to the outcome via SERVES,
    # not to a lever), and the un-modelled intermediary layer shows as one
    # platform-limit note, never a per-goal "no path" alarm.
    assert "Levers — you act" in _HTML
    assert "Serving work — Padhanam sees" in _HTML
    assert "intermediaries not modelled" in _HTML
    assert "map-platform-note" in _HTML


def test_coverage_view_is_a_live_sibling_of_the_goals_view():
    # D193/S98: the unlinked pile lives in its own coverage view, a live sibling.
    assert '{ id: "coverage", label: "Coverage", live: true }' in _HTML
    cov = _coverage_template()
    assert 'id="coverage-list"' in cov
    assert "loadUnlinked()" in cov


def test_coverage_view_lists_items_by_type_with_dates_no_linking():
    # AC1/AC2: the view groups unlinked units by type and shows a date, framed as
    # coverage; it offers NO manual link-to-goal action.
    cov = _coverage_template()
    # the coverage framing (matcher's job, not the operator's hand)
    assert "matcher" in cov.lower()
    assert "don't link them by hand" in cov
    # the renderer groups by type and shows a formatted date
    assert "function loadUnlinked" in _HTML
    assert "function coverageRow" in _HTML
    assert "fmtDate(u.occurred_at)" in _HTML
    assert "FACET_LABEL" in _HTML
    # no manual-link action affordance: coverage rows carry no link handler,
    # no "link to goal" button, no link endpoint call.
    assert "function coverageRow" in _HTML
    assert "linkToGoal" not in _HTML
    assert "data-link-goal" not in _HTML
    assert ">Link</" not in _HTML
    # the coverage row renderer attaches no click handler (read-only items)
    cov_row = _HTML[_HTML.index("function coverageRow") : _HTML.index("async function loadUnlinked")]
    assert "addEventListener" not in cov_row
    assert ".onclick" not in cov_row


def test_daily_surface_no_longer_carries_the_orphan_pile():
    # AC3: the dash drops the orphan fold; a small count links to the coverage
    # view instead.
    assert "function orphanFoldEl" not in _HTML  # the pile renderer is gone
    assert '"coverage-link"' in _HTML  # the small pointer's class
    assert 'goto("coverage")' in _HTML


# --- S103a / S103a-fix: the authored-CDD lens affordances -------------------


def test_cdd_lens_carries_add_and_reclassify_affordances():
    # S103a: the add control and the reclassify select render on the CDD lens.
    assert "function cddAddControl" in _HTML
    assert "cdd-reclass" in _HTML and "Move to" in _HTML


def test_cdd_edit_affordance_is_inline_over_the_existing_correct_path():
    # S103a-fix AC1: a clear in-place edit control on each element AND the
    # outcome, wired to the existing S102 correct path (no new write path).
    assert "function cddBeginEdit(" in _HTML
    assert 'edit.textContent = "Edit"' in _HTML
    assert "cddBeginEdit(row, el.label," in _HTML          # element edit
    assert "cddBeginEdit(row, cdd.expected_outcome," in _HTML  # outcome edit
    assert "/correct" in _HTML
    # in place, not a blocking prompt dialog (the unrecognisable old affordance)
    assert 'window.prompt("Edit' not in _HTML


def test_cdd_lens_shows_element_evidence_and_the_unbound_bucket():
    # S103b/D202: the lens shows per-element unit counts (where signal landed) and
    # the unbound bucket (units matching no element), read-only from /cdd/evidence.
    assert '"/daily-driver/cdd/evidence"' in _HTML
    assert "cdd-evidence" in _HTML
    assert "unbound" in _HTML.lower()


def test_cdd_lens_is_interactive_relink_unlink_rematch():
    # S103c/D203: the evidence display is interactive — a re-match trigger, and
    # per-element bound units with relink/unlink (over the read-only S103b display).
    assert '"/daily-driver/cdd/rematch"' in _HTML
    assert '"/daily-driver/cdd/bindings"' in _HTML
    assert '"/daily-driver/cdd/evidence/relink"' in _HTML
    assert '"/daily-driver/cdd/evidence/unlink"' in _HTML
    assert "function renderBindings" in _HTML
    assert "Re-match" in _HTML


def test_cdd_bindings_show_rationale_and_match_strength():
    # S103c-fix: each binding shows the why (matched term) + a match-strength band
    # labelled as strength (not correctness); recomputed on read.
    assert "matched on" in _HTML            # the why
    assert "cdd-strength" in _HTML          # the strength badge
    assert "match strength, not" in _HTML   # the honest framing in a tooltip


def test_cdd_bindings_are_triageable_and_unlink_stays_expanded():
    # S103c-fix: weakest-first triage with a weak-only filter; an unlink re-renders
    # the list in place (subRefresh) rather than collapsing the body; bulk unlink.
    assert "weak matches only" in _HTML
    assert "function subRefresh" in _HTML or "subRefresh = async" in _HTML
    assert "Unlink selected" in _HTML  # bulk path


def test_list_and_map_can_correct_from_one_shared_source():
    # S103c-fix-2: List and Map gain unlink + element-level relink, over the same
    # element-evidence bindings the CDD view uses (loaded once in loadAssess), and
    # reuse the S103c correction paths (no new write path).
    assert "function renderGoalCorrections" in _HTML
    assert "function relinkPicker" in _HTML
    # one shared source: bindings loaded in loadAssess, used by all three views
    assert "cddBindings = await api" in _HTML
    assert "loadAssess" in _HTML
    # corrections from List AND Map fold bodies
    assert _HTML.count("renderGoalCorrections(body, grp)") >= 2
    # reuse the S103c paths, not a new write path
    assert '"/daily-driver/cdd/evidence/unlink"' in _HTML
    assert '"/daily-driver/cdd/evidence/relink"' in _HTML
    assert "Relink to goal" in _HTML  # the cross-goal element picker


def _fn_body(name: str) -> str:
    start = _HTML.index(f"function {name}(")
    # crude: the body up to the next top-level "function " at the same indent.
    nxt = _HTML.find("\n    function ", start + 1)
    return _HTML[start: nxt if nxt != -1 else len(_HTML)]


def test_correction_interaction_is_single_sourced():
    # S103c-fix-4 (the structural single-source guard, reflection 1): the
    # correction interaction lives in ONE component; a future view that
    # re-implemented its own would duplicate the bulk control / the unlink call.
    assert "function renderCorrectionList" in _HTML
    # the unlink ACTION is single-sourced (one POST site, in unlinkBinding) — a
    # second correction implementation would add another.
    assert _HTML.count('"/daily-driver/cdd/evidence/unlink"') == 1
    # the bulk control + the bulk-select checkbox live in the shared source only
    shared = _fn_body("renderCorrectionList")
    assert 'textContent = "Unlink selected"' in shared and "cdd-pick" in shared
    assert _HTML.count('textContent = "Unlink selected"') == 1
    # both view renderers DELEGATE to the shared source, not re-implement it
    assert "renderCorrectionList(" in _fn_body("renderBindings")
    assert "renderCorrectionList(" in _fn_body("renderGoalCorrections")


def test_correction_row_shows_why_and_strength_consistently():
    # AC4: the why + strength render from the one source (so all three views match).
    src = _fn_body("renderCorrectionList")
    assert "matched on" in src and "cdd-strength" in src


def test_draft_missing_has_a_clear_empty_state():
    # S103a-fix AC2: draft-missing reads the existing zero-count + skipped_existing
    # flag and shows a clear "all already have a CDD" state, not a silent zero.
    assert "All goals already have a CDD" in _HTML
    assert "x.skipped_existing" in _HTML


def test_raw_tasks_and_goal_readings_cut_from_the_surface():
    # The raw ingested-tasks dump and the standalone goal-readings block are cut
    # from every user-facing view (their endpoints stay; this is render-only).
    assert "function loadTasks" not in _HTML
    assert "function loadGoals" not in _HTML
    assert 'id="tasks"' not in _HTML
    assert 'id="goals"' not in _HTML
