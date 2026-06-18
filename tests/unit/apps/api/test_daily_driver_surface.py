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


def test_raw_tasks_and_goal_readings_cut_from_the_surface():
    # The raw ingested-tasks dump and the standalone goal-readings block are cut
    # from every user-facing view (their endpoints stay; this is render-only).
    assert "function loadTasks" not in _HTML
    assert "function loadGoals" not in _HTML
    assert 'id="tasks"' not in _HTML
    assert 'id="goals"' not in _HTML
