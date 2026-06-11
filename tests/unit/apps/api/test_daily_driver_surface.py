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
    end = _HTML.index("} else {", start)
    return _HTML[start:end]


def test_today_renders_list_and_history_only():
    today = _today_template()
    assert 'id="list"' in today
    assert 'id="history-section"' in today
    for cut in ('id="goals"', 'id="tasks"', 'id="moat"', 'id="suggestions"'):
        assert cut not in today, f"{cut} must not render on Today (D182)"


def test_dash_view_live_and_holds_moat_and_suggestions():
    assert '{ id: "dash", label: "How am I doing", live: true }' in _HTML
    dash = _dash_template()
    assert 'id="moat"' in dash
    assert 'id="suggestions"' in dash
    assert "loadUnitsByGoal()" in dash


def test_raw_tasks_and_goal_readings_cut_from_the_surface():
    # The raw ingested-tasks dump and the standalone goal-readings block are cut
    # from every user-facing view (their endpoints stay; this is render-only).
    assert "function loadTasks" not in _HTML
    assert "function loadGoals" not in _HTML
    assert 'id="tasks"' not in _HTML
    assert 'id="goals"' not in _HTML
