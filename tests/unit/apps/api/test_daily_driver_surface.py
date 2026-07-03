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


def test_act_lens_renders_the_substrate_in_order():
    # S103z/D232: the act read's items render in their proposed (urgency) order
    # via actRow — the pre-S103z render(data.items) worklist is retired.
    assert "async function loadAct()" in _HTML
    assert 'await api("/daily-driver/act")' in _HTML
    assert "items.forEach((it) => list.appendChild(actRow(it)))" in _HTML


def test_act_row_meta_is_source_tag_plus_action_no_domain_word():
    # AC4/D232: the row meta carries the source tag + the read's action line —
    # no domain/tier word composed in (tint carries the source).
    assert 'class="act-src"' in _HTML
    assert "${escapeHtml(it.action)}" in _HTML


_ROUTER = (
    Path(__file__).resolve().parents[4]
    / "apps" / "api" / "routers" / "daily_driver.py"
).read_text()


def test_today_endpoints_untouched_server_side():
    # AC6: render-only — the server's /today read and the /today/order endpoint
    # are unchanged (only the client reorder affordance was removed).
    assert '@router.get("/today"' in _ROUTER
    assert '"/today/order"' in _ROUTER


# --- S103z (D232): the act lens — Today/Week/doing over one substrate ---------


def test_act_lens_toggle_has_today_week_doing():
    today = _today_template()
    assert 'id="act-toggle"' in today
    for seg in ('data-act="today"', 'data-act="week"', 'data-act="doing"'):
        assert seg in today
    assert "loadAct()" in today


def test_act_horizon_and_doing_filter():
    # Today = due <= 0; Week = due <= 7; doing = live-opportunity items (D232).
    assert 'if (actMode === "today") return it.due_in_days <= 0;' in _HTML
    assert 'if (actMode === "week") return it.due_in_days <= 7;' in _HTML
    assert "return it.is_opportunity;" in _HTML  # doing


def test_act_preserves_the_commitment_calendar_case_drawers_and_writes():
    # Opportunity items open the pipeline process detail; commitment/calendar/case
    # items rebuild the today-item shape their existing drawer reads, so the
    # D157/D162/S60 loops and their writes are preserved (D232).
    assert "function openActItem(" in _HTML
    assert "openProcessDetail(it.ref.opportunity_id" in _HTML
    assert "openItem(keyOf(t))" in _HTML
    assert "/daily-driver/commitments/${it.item_id}/completions" in _HTML  # Did-it
    assert "await loadAct()" in _HTML  # a write refreshes the act lens


def test_act_lens_uses_tokens_not_colour_literals():
    # AC5/D232: the act-lens styling inherits the S103y tokens (dark-mode safe) —
    # the source tints and the dot are var(...), never a hardcoded hex.
    assert "const ACT_SRC_TINT" in _HTML
    tint_block = _HTML[_HTML.index("const ACT_SRC_TINT"):_HTML.index("const ACT_HINT")]
    assert "#" not in tint_block  # no hex literals in the source-tint map
    assert "var(--teal)" in tint_block and "var(--warm)" in tint_block
    assert "background: var(--tint)" in _HTML  # the .act-dot


def test_week_nav_placeholder_retired():
    # D232: only the Week nav placeholder is retired (folded into the act lens's
    # Week horizon); the Today nav item and the /today endpoints stay.
    assert '{ id: "week"' not in _HTML
    assert '{ id: "today", label: "Today", live: true }' in _HTML


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


def test_today_holds_the_act_lens_not_the_dash_internals():
    # One lens per view (D182): the act lens carries its list + toggle, and does
    # not pull the dash/moat internals.
    today = _today_template()
    assert 'id="list"' in today
    assert 'id="act-toggle"' in today
    for cut in ('id="goals"', 'id="tasks"', 'id="moat"', 'id="suggestions"'):
        assert cut not in today, f"{cut} must not render on the act lens (D182)"


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
    # D199/S101 + S103y/D231: the assess surface reads the cached units-by-goal
    # source (assessData) with no second data path. The standalone "List" tab is now
    # the by-goal altitude inside the folded Assessment tab (renderAssessList remains,
    # called by renderAssessment); the Map tab stays.
    dash = _dash_template()
    assert 'id="assess-toggle"' in dash
    assert 'data-mode="assessment"' in dash and 'data-mode="map"' in dash
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
    # D212: each binding shows a prominent WHY-LINKED basis row (the discriminative
    # term, or a "no clear basis" flag) + a match-strength band labelled as strength
    # (not correctness); recomputed on read.
    assert "why linked" in _HTML            # the basis row label (leg 1)
    assert "cdd-basis-term" in _HTML        # the discriminative-term presentation
    assert "no clear basis" in _HTML        # the generic-only flag
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


def test_pipeline_stats_tab_split_ladder_kanban_restage():
    # D217: a Pipeline stats tab (additive) — three-way split, depth ladder, engaged
    # Kanban with drag-to-re-stage + a next-best-action; Doing is untouched.
    assert 'data-mode="pipeline"' in _HTML
    assert "function renderAssessPipeline" in _HTML and "function buildPipeline" in _HTML
    p = _fn_body("buildPipeline")
    assert "/cdd/pipeline-stats/" in _fn_body("renderAssessPipeline")
    assert "split by outcome" in p and "Depth ladder" in p and "pipe-kanban" in p
    assert "not summed" in p  # the grain honesty (no faked total)
    # drag-to-re-stage writes the gate (the proof action)
    assert "/stage" in p and 'setData("text/opp"' in _fn_body("pipeCard")
    assert "next_action" in _fn_body("pipeCard")
    # additive: the Doing render + the assessment endpoint are still present, untouched
    assert "function renderAssessDoing" in _HTML and "/cdd/assessment/" in _HTML


def test_process_detail_view_and_close_from_board():
    # D219: a process is a first-class object — a detail view (thread, sources,
    # binds, stage picker, next action, close) opened from any card, plus a
    # close control on active cards. Pure assembly, reuses the built pieces.
    assert "function openProcessDetail" in _HTML and "function renderProcessDetail" in _HTML
    d = _fn_body("renderProcessDetail")
    # the detail assembles the reused pieces
    assert "Correspondence" in d and "bindingSourceBlock(" in d   # thread + openable source
    assert "renderCorrectionList(" in d                           # binds verification drawer
    assert "/stage" in d                                          # the stage picker (gate write)
    assert "next_action" in d                                     # the NBA
    assert "closeReasonPicker(" in d                              # the close row
    # close-with-outcome reuses the S103n /close write
    assert "/close" in _fn_body("closeReasonPicker")
    # open-from-card: active + closed cards, the lens, and the Map opp chips
    assert "openProcessDetail(" in _fn_body("pipeCard")
    assert "openProcessDetail(" in _fn_body("closedCard")
    assert "openProcessDetail(" in _fn_body("buildLensSelector")
    assert "openProcessDetail(" in _fn_body("buildFlowSpine")
    # close-from-board: an active card carries the close-with-outcome picker
    assert "closeReasonPicker(c.opportunity_id, opts.reload)" in _fn_body("pipeCard")


def test_pipeline_board_splits_active_from_closed_record():
    # D218: the board splits — active board is live-only, closed record is grouped
    # by outcome with stage-at-close; closed cards carry no next action.
    p = _fn_body("buildPipeline")
    assert "Active board" in p and "live processes only" in p
    assert 'c.status !== "closed"' in p          # active board filters to live
    assert "Closed record" in p and "by outcome" in p
    assert "Nothing is live" in p                # the honest empty active board
    # active cards carry the action + drag; closed cards do not
    pc = _fn_body("pipeCard")
    assert "opts && opts.active" in pc and "active ?" in pc  # action/drag gated on active
    cc = _fn_body("closedCard")
    assert "died at:" in cc and "next_action" not in cc      # stage-at-close, no action
    # the stage-at-close setter reuses the gate write
    assert "Set stage-at-close" in cc and "/stage" in cc


def test_how_am_i_doing_assessment_render():
    # D216 + S103y/D231: the verdict is the "verdict" altitude of the folded
    # Assessment tab (renderAssessDoing, reached via renderAssessment) reading
    # /cdd/assessment; the close-reason split is flagged proof-dependent, never the
    # verdict's basis.
    assert 'data-mode="assessment"' in _HTML
    assert "function renderAssessment" in _HTML
    assert "function renderAssessDoing" in _HTML and "function buildAssessment" in _HTML
    doing = _fn_body("renderAssessDoing")
    assert "/cdd/assessment/" in doing
    body = _fn_body("buildAssessment")
    assert "Because" in body and "Move" in body           # recommendation-shaped
    assert "split_proof_dependent" in body                # the proof-dependent split
    assert "does not depend on which" in body             # the headline-independence note


def test_opportunity_lens_scopes_thread_flow_and_binds():
    # D213: the opportunity lens — a selector (All / opportunities / unclustered),
    # a correspondence thread, a flow gate highlight, and binds scoped to the lens.
    assert "function buildLensSelector" in _HTML
    assert "function buildThreadPanel" in _HTML
    assert "function lensMatch" in _HTML
    # the honest unclustered entry (coverage honesty, D171)
    assert "Unclustered" in _HTML
    # the selector lists the opportunities from the CDD read
    assert "cdd.opportunities" in _fn_body("buildLensSelector")
    # the binds drawer scopes to the lens (proof per opportunity)
    assert "lensMatch(b)" in _fn_body("renderBindings")
    # the flow marks the lens opportunity's gate
    assert "lens-here" in _fn_body("buildFlowSpine")
    # the thread time-orders the opportunity's units and opens their source
    thread = _fn_body("buildThreadPanel")
    assert "occurred_at" in thread and "bindingSourceBlock(" in thread


def test_opportunity_close_state_in_the_lens():
    # D214: the lens marks closed opportunities with their reason, the live set is
    # live-only, and a close/reopen control acts on the selected opportunity.
    assert "function buildCloseControl" in _HTML
    sel = _fn_body("buildLensSelector")
    assert "the live set" in sel              # All counts live only
    assert "closed:" in sel                   # closed opportunities marked with reason
    assert "buildCloseControl(" in sel        # the close/reopen control wired in
    ctl = _fn_body("buildCloseControl")
    assert "/close" in ctl and "/reopen" in ctl  # both actions
    # D215: a system-suggested (extracted) opportunity carries confirm/reject proof
    assert "system_suggested" in ctl
    assert "/confirm" in ctl and "/reject" in ctl
    assert "reason: reason.value" in ctl or "reason:" in ctl  # close sends a reason
    # the flow marks a closed opportunity at its gate as closed, not live
    assert "closed:" in _fn_body("buildFlowSpine")


def test_goal_and_process_corrections_dedupe_by_unit():
    # D219-fix: a whole-goal/process corrections list dedupes by unit (a unit bound
    # to several elements repeats once per element otherwise — the "duplicates in
    # the list"); renderCorrectionList keeps the weakest bind + a "+N" hint.
    rl = _fn_body("renderCorrectionList")
    assert "opts.dedupeByUnit" in rl and "moreByUnit" in rl
    # the whole-goal + whole-process callers dedupe; the per-element drawer does not
    assert "dedupeByUnit: true" in _fn_body("renderGoalCorrections")
    # D219-fix: the goal corrections list is a shrinking queue — corrected
    # (user_owned) units leave it, with a "corrected" count for progress.
    gc = _fn_body("renderGoalCorrections")
    assert "!b.user_owned" in gc and "corrected" in gc
    assert "dedupeByUnit: true" in _fn_body("renderProcessDetail")
    assert "dedupeByUnit" not in _fn_body("renderBindings")  # per-element: no dedupe


def test_correction_row_shows_why_and_strength_consistently():
    # D212: the basis row + strength + the openable source all render from the one
    # shared list (so every view — Map drawer + the flat lens — matches).
    src = _fn_body("renderCorrectionList")
    assert "cdd-strength" in src
    assert "bindingBasisRow(" in src      # leg 1: the discriminative basis row
    assert "openableSource(" in src       # leg 2: the openable source (D235: on-demand, was bindingSourceBlock)


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


def test_cdd_renders_process_flow_gate_sections():
    # S103g (D207): the CDD lens renders the flow as gate portal sections, each
    # opening into its local CDD (gate-scoped elements grouped by kind).
    assert "cddGateSection" in _HTML
    assert "Process flow" in _HTML
    # gate-scoped elements are split from goal-level by gate_id.
    assert "e.gate_id" in _HTML
    assert "cdd.gates" in _HTML


def test_cdd_renders_opportunities_under_gates():
    # S103h (D208): the flow shows opportunities, a per-opportunity summary, and
    # each opportunity's gate position + unit count.
    assert "cdd.opportunities" in _HTML
    assert "cdd-opp-summary" in _HTML
    assert "current_gate_id" in _HTML
    assert "Opportunities here" in _HTML


def test_map_renders_the_real_causal_graph():
    # S103j (D210): the Map draws the real graph — control CDD, flow spine with
    # gate portals, opportunities, disposition strip — and node-tap opens proof.
    assert "buildCausalMap" in _HTML
    assert "buildFlowSpine" in _HTML and "buildGatePortal" in _HTML
    assert "openProofNode" in _HTML            # node-tap -> proof drawer
    assert "drawEdges" in _HTML                # directed causal edges
    assert "map-disp" in _HTML                 # disposition summary
    # the old depth-two sibling-feeder stopgap note is gone
    assert "aren't modelled yet, so that link reads broken" not in _HTML


def test_map_teal_is_interactive_only():
    # design-language §4: teal only on interactive/active affordances. Since S103y/D231
    # teal is the --teal token (light+dark), not a hardcoded literal, so the panels
    # adapt to dark mode; the literal now lives only in the :root token definition.
    assert "var(--teal)" in _HTML                     # used for interactive/active states
    assert "--teal: #2ba692" in _HTML                 # the dark token definition


def test_units_by_goal_endpoint_does_not_pass_email_source_metadata():
    # S103j regression: an S103i sed added email_source_metadata to the
    # list_units_by_goal call (which doesn't accept it), 500ing the assess view.
    # Guard the call shape: only correlate_goal_facets takes that kwarg.
    import inspect
    from contexts.daily_driver.application.list_units_by_goal import (
        list_units_by_goal,
    )
    assert "email_source_metadata" not in inspect.signature(list_units_by_goal).parameters
    src = (
        Path(__file__).resolve().parents[4]
        / "apps" / "api" / "routers" / "daily_driver.py"
    ).read_text()
    # the list_units_by_goal( ... ) call block must not carry the kwarg
    call = src.split("grouped = await list_units_by_goal(")[1].split(")")[0]
    assert "email_source_metadata" not in call


def test_origination_lead_column_renders_with_form_and_apply():
    # S103t/D221: the active board has an origination Lead column at its left — a
    # create-lead form (POST /cdd/lead) + lead cards each with an apply action that
    # advances the lead to Apply via the /stage write. The empty Lead gate column is
    # filtered out of the normal gate columns (leads render in the origination
    # column instead).
    assert "function buildLeadColumn(" in _HTML
    assert "kan.appendChild(buildLeadColumn(" in _HTML
    assert '"/daily-driver/cdd/lead"' in _HTML          # create-lead POST
    assert "Add lead" in _HTML                            # the form submit
    assert 'name="fit_tier"' in _HTML
    assert 'name="warm_access_available"' in _HTML
    assert 'name="origination_source"' in _HTML
    # the apply action advances Lead -> Apply via the existing stage write
    assert 'g.name === "Application"' in _HTML
    assert "/stage" in _HTML
    # the Lead gate is not double-rendered as an empty normal column
    assert 'g.name !== "Lead"' in _HTML


def test_contacts_proof_panel_and_inline_contacts_render():
    # S103u/D222: the pipeline view carries a contact proof panel (add + confirm /
    # enrich / reject) and a lead card renders its linked contacts inline + the
    # contact-specific warming next-best-action.
    assert "function buildContactsPanel(" in _HTML
    assert "wrap.appendChild(buildContactsPanel(" in _HTML
    assert '"/daily-driver/cdd/contacts"' in _HTML            # list + add
    assert "/confirm" in _HTML and "/enrich" in _HTML and "/reject" in _HTML
    assert "Add contact" in _HTML
    # inline contacts + warming NBA on the lead card
    assert "lead-contacts" in _HTML
    assert "lead-warm-nba" in _HTML
    assert "le.warming_action" in _HTML
    assert "le.contacts" in _HTML
    # capture_source, never the reused 'source' name, on the add form
    assert 'name="capture_source"' in _HTML


def test_contact_network_map_and_warming_surface():
    # S103v/D225: the contacts panel has a List/Map toggle; the map groups by company
    # with leads + derived-warm + a per-contact warming block (D224).
    assert "function renderContactsMap(" in _HTML
    assert "function buildContactsPanel(s, reload)" in _HTML
    assert "buildContactsPanel(s, reload)" in _HTML          # called with pipeline stats
    assert "cmap-toggle" in _HTML                            # List/Map toggle
    assert "function warmingBlock(" in _HTML
    assert '"/daily-driver/cdd/warming"' in _HTML            # log a warming step
    assert "/daily-driver/cdd/warming/" in _HTML             # read steps per subject
    assert "proofed — warm derives" in _HTML                 # honest unproofed note (D171)


def test_qualification_panel_activity_log_and_stage_rename():
    # S103w: the process detail view carries a soft-activated qualification panel + an
    # activity log; the ladder renamed Apply->Application; In role relabels won.
    assert "function buildQualificationSection(" in _HTML
    assert "function buildActivitySection(" in _HTML
    assert "buildQualificationSection(grp, oppId, card, reload)" in _HTML
    assert "/cdd/qualification/" in _HTML                     # read qualification
    assert "/qualification" in _HTML                          # set a field
    assert "/activity" in _HTML                               # log + read activity
    assert "qual-row" in _HTML and "qual-stale" in _HTML      # soft activation + risk badge
    # the Apply->Application rename + In-role relabel
    assert 'g.name === "Application"' in _HTML
    assert '"Application"' in _HTML and '"Interviewing"' in _HTML and '"Offer"' in _HTML
    assert '["won", "In role / hired"]' in _HTML


def test_capture_source_renders_set_valued():
    # S103x/D230: capture_source is set-valued — the UI joins the channels.
    assert '(c.capture_source||[]).join(" + ")' in _HTML


def test_s103y_surface_consolidation():
    # S103y/D231: token consolidation, the assessment fold, the cross-link, drill fix.
    # 1. tokens: the S103t-x panels no longer hardcode teal/warm (they use vars, dark-mode safe).
    #    Only the :root token DEFINITIONS may carry the literals.
    import re
    non_def = [l for l in _HTML.split("\n")
               if not re.match(r'\s*--[\w-]+:\s*#', l)]
    body = "\n".join(non_def)
    assert "#2BA692" not in body and "#1a8070" not in body and "#b0997e" not in body
    assert "var(--teal)" in _HTML and "var(--warm)" in _HTML
    # 2. shared capture-source badge (was duplicated in contactRow + the contact map)
    assert "function captureSourceBadge(" in _HTML
    assert _HTML.count('${captureSourceBadge(c)}') == 2   # two call-sites, one render
    # 3. the assessment fold: one Assessment tab + a Verdict/By-goal altitude sub-toggle;
    #    the separate Doing + List tabs are gone.
    assert 'data-mode="assessment"' in _HTML
    assert 'data-mode="list"' not in _HTML and 'data-mode="doing"' not in _HTML
    assert "function renderAssessment(" in _HTML and "assessAltitude" in _HTML
    # 4. the pipeline -> assessment inline cross-link
    assert 'switchAssess("assessment")' in _HTML and "assess-xlink" in _HTML
    # 5. the drill-filter fix: a drill-aware empty state, not "every process is closed"
    assert "No live processes in" in _HTML and "Clear filter" in _HTML


def test_by_goal_drill_down_shows_workstreams_not_the_moat():
    # D234: the by-goal drill-down shows the goal's WORKSTREAMS (opportunities with
    # status), each drilling into the D219 process detail; the ingested-email moat
    # is retired from the assessment body (it relocated to the corrections block).
    assert "async function renderGoalWorkstreams(" in _HTML
    ws = _HTML[_HTML.index("async function renderGoalWorkstreams("):
               _HTML.index("async function renderGoalWorkstreams(") + 2000]
    # reads the goal's opportunities by outcome (N-goal-ready), renders pipeCards
    assert "/daily-driver/cdd/pipeline-stats/${grp.outcome_id}" in ws
    assert "pipeCard(c, { grp: { outcome_id: grp.outcome_id } })" in ws  # drills to D219
    # verdict-first still holds: the drill body (verdictLineEl) calls the renderer
    assert "renderGoalWorkstreams(wsWrap, grp)" in _HTML
    # the moat (moatRow) and the S103aa evidence toggle are gone from the surface
    assert "function moatRow(" not in _HTML
    assert "makeFold(evHead" not in _HTML
    # the moat relocated: the corrections block names the ingested work bound here
    assert "Ingested work bound here" in _HTML


def test_verification_source_is_on_demand_not_inline_by_default():
    # D235: no raw email body renders in any surface body by default; the openable
    # source (D212) opens on a click everywhere (verification surfaces included),
    # enforcing D233 with no carve-out and superseding D212's source-by-default.
    import re
    # the inline-by-default append (the one source of all four sites' drift) is gone;
    # renderCorrectionList now routes the source through the click-to-open toggle.
    assert "card.appendChild(bindingSourceBlock" not in _HTML
    assert "function openableSource(" in _HTML
    assert "card.appendChild(openableSource(b))" in _HTML
    assert "src-toggle" in _HTML  # the click-to-open control (button className + CSS)
    # every place that paints the email body does so LAZILY, inside a click handler
    # guarded by !src.dataset.built — 3 sites (openableSource + the 2 thread panels),
    # all guarded; no unguarded body paint remains.
    appends = re.findall(r"appendChild\(bindingSourceBlock\(b\)\)", _HTML)
    guarded = re.findall(r"!src\.dataset\.built.{0,50}appendChild\(bindingSourceBlock\(b\)\)", _HTML)
    assert len(appends) == 3 and len(guarded) == 3
