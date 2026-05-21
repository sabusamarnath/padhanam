# Private Assistant Platform Specification

Reference document, not binding architectural specification. Operator-supplied product specification for a governed Private Assistant Platform. Preserved here per Phase 2-A P13 framing brief Decision 6 option (c) for cross-reference at Phase 2-A substrate verification, Phase 2-B surface extension, and Phase 3+ framing.

The spec's substrate primitives largely map to Padhanam's commitments at Phase 2; specific extracts land as charter additions at P13 framing substantive conversation. The spec's surface architecture (Studio plus Portal SPA) and customer-organisation ICP do not match Phase 2-A's messaging-first delivery plus senior-leader-ICP commitment; those surface elements defer to Phase 2-B and Phase 3+ extension review.

Source file: operator upload, 2026-05-20.

---

# Product Specification — Governed Agentic AI Development Platform

> **Working name:** "the Platform" — a placeholder. Replace with your chosen brand throughout.
> **Document type:** Full product, UI, and UX specification.
> **Audience:** Designers, engineers, and AI build tools generating the product.

---

## 1. Product Overview

### 1.1 What it is

The Platform is a B2B SaaS product for **building, deploying, and governing agentic AI workflows inside enterprise organisations**. It lets non-engineers compose AI agents into multi-step workflows, run those workflows against real work, and keep every decision under human governance with a complete audit trail.

The category claim is **"the governed agentic AI development platform."** Competitors automate work; the Platform automates work *and* makes every automated decision accountable, reversible, attributable, and auditable.

### 1.2 The problem

Enterprises want to use AI agents for real operational work — claims triage, content production, document intake, compliance review — but cannot, because:

- AI output is not trusted without a human in the loop.
- There is no record of *why* an automated decision was made, *what* data informed it, or *which model version* produced it.
- Model providers ship silent upgrades that change agent behaviour with no warning.
- Compliance teams cannot sign off on a black box.

### 1.3 The solution

The Platform delivers four things together:

1. **Authoring** — a visual builder for AI agents and the workflows that orchestrate them, usable by operations staff, not just engineers.
2. **Governed execution** — every workflow run pauses for human review at defined gates; nothing consequential happens silently.
3. **Provenance & lineage** — every data point carries its full history (who asserted it, how, when, with what certainty); every run records the exact model and version used.
4. **Lifecycle governance** — agents and the AI models they depend on are versioned, pinned, promoted through environments, and impact-assessed before change.

### 1.4 Core product principle

**Simplicity on the surface, governance underneath.** The user-facing experience must feel light. All governance, audit, provenance, and certainty machinery operates below the surface and only surfaces when the user needs it. If configuration feels heavy, the design is wrong.

---

## 2. Personas & Roles

The Platform serves two distinct audiences through two distinct surfaces.

### 2.1 Builders & operators (the Studio)

People who design and operate AI workflows.

| Role | Primary job | Surface |
|---|---|---|
| **Platform Admin** | Operates the Platform itself across all customer organisations. Curates the model catalogue, defines platform-wide governance standards. | Admin + Studio |
| **Organisation Admin** | Manages one customer organisation: users, environments, model configuration, integrations, organisation-level governance policy. | Admin + Studio |
| **Manager** | Owns workflow operations for a team. Reviews runs, manages promotions, oversees builders. | Studio |
| **Builder** | Designs agents and workflows. The primary authoring persona. | Studio |
| **Reviewer** | Actions human-in-the-loop review gates. Approves, rejects, corrects, escalates. | Review / Tasks |
| **Observer** | Read-only visibility into workflows and runs. | Studio (read-only) |

### 2.2 Requesters (the Portal)

People who *use* the workflows others have built.

| Role | Primary job | Surface |
|---|---|---|
| **Portal Requester** | Submits requests into a workflow and tracks their progress. Never sees pipeline internals. | Portal |
| **API Caller** | A connected external application that triggers workflows programmatically. | API only |

### 2.3 Role hierarchy

```
Platform Admin → Org Admin → Manager → Builder → Reviewer → Observer → Portal Requester → API Caller
```

Higher roles inherit the capabilities of lower roles. Permissions are enforced server-side at every endpoint and reflected in the UI (hidden actions, disabled controls, role-gated navigation items).

---

## 3. Key Concepts & Glossary

| Concept | Definition |
|---|---|
| **Agent** | A reusable AI capability with a defined purpose, instructions, acceptance criteria, and output shape. The unit of authored work. |
| **Agent Version** | An immutable, named snapshot of an agent at a point in time. Agents are referenced by pinned version. |
| **Workflow** | An ordered graph of steps (agents, gates, merges) that processes a request end to end. |
| **Workflow Definition** | The authored specification of a workflow. Has a lifecycle (draft → published) and immutable published versions. |
| **Step** | One node in a workflow: an *agent step*, a *gate step*, or a *merge step*. |
| **Run** | One execution of a workflow against one request. |
| **Signal** | A named, typed value produced by a step and consumed by later steps. The data flowing through a workflow. |
| **Gate** | A defined pause point where a human must decide before the run continues. |
| **Gate Action** | The human's decision at a gate: approve, reject, redirect, override, correct, provide input, decline, resolve conflict. |
| **Case** | The real-world entity a workflow governs (a project, a claim, an invoice). Stable identity that outlives any one run. |
| **Data Point** | A logical field on a Case (e.g. "risk level"). |
| **Assertion** | One recorded value for a Data Point, with full provenance. Assertions layer over time; originals are never erased. |
| **Provenance** | The record of *how* a value was obtained: human override, system-injected, AI-extracted, or inferred. |
| **Certainty** | A confidence score, tracked separately for data certainty (declared at entry) and outcome certainty (computed). |
| **Environment** | A pipeline stage: Dev, SIT, UAT, Prod (configurable). Where workflows and agents run with stage-appropriate governance. |
| **Promotion** | The governed act of moving an agent, workflow, or model configuration from one environment to the next. |
| **AI Provider** | A company operating AI inference endpoints. |
| **Model Version** | A specific AI model release. |
| **Model Configuration** | The operational binding of a model version + provider account + runtime parameters. Agents bind to one. |
| **Governance Tap** | A governance check that runs automatically before/after a step or on a signal, without being wired into the visible flow. |
| **Output Contract** | The declared shape of a workflow's result: render mode, fields, formatting, conditional visibility. |
| **Intake** | The validation and scoring stage every incoming request passes through before execution. |

---

## 4. Information Architecture & Navigation

### 4.1 Two front doors

- **Studio** — `/studio/*` — the builder/operator workspace. Default landing for Builder, Manager, Admin, Observer.
- **Portal** — `/portal/*` — the requester surface. Default landing for Portal Requester.

A user with both roles sees a surface switcher in the top bar.

### 4.2 Studio navigation (left sidebar)

| Item | Purpose | Min role |
|---|---|---|
| **Dashboard** | Activity overview: active runs, gates awaiting me, recent agents. | Observer |
| **Agents** | Browse, create, edit, version, and promote agents. | Builder |
| **Workflows** | Browse and author workflows on the canvas. | Builder |
| **Runs** | Monitor running and completed workflow runs. | Observer |
| **My Tasks** | Review gates assigned to me. | Reviewer |
| **Trials** | Run and adjudicate authoring-time variant tests. | Builder |
| **Evaluation** | Manage governance artefacts and evaluation rubrics. | Manager |
| **Integrations** | Webhooks and external connections. | Org Admin |
| **Audit** | Search the audit trail. | Manager |
| **Admin** | Users, environments, models, organisation settings. | Org Admin |

### 4.3 Portal navigation (top bar)

| Item | Purpose |
|---|---|
| **My Requests** | List of the requester's submitted requests. |
| **New Request** | Start a new request against an available workflow. |

### 4.4 Global chrome

- **Top bar:** product mark (left), environment indicator, global search, notifications bell, user menu (right).
- **Environment indicator:** a coloured tag showing the active environment. Always visible. Colour-coded (see §6.4).
- **Breadcrumbs:** below the top bar on detail pages.

---

## 5. Design Principles

These govern every design and build decision.

### 5.1 Experience principles

1. **Simplicity is paramount.** The interface is always as simple as it can be. Complexity lives underneath. If something feels heavy to configure or explain, simplify it.
2. **Innovate, then apply consistently.** When a better pattern is found, it becomes the standard and is applied everywhere it fits.
3. **Fast, safe, consistent, trusted.** Feedback is immediate. Irreversible actions are clearly marked. A pattern learned once applies everywhere. Nothing happens silently — the user always knows what the system is doing and why.

### 5.2 Platform principles

4. **Control what you own; influence what you don't.** Accept only what is valid.
5. **Validate at every boundary.** Every entry point validates what enters it. Bad data is caught at the boundary, not discovered inside.
6. **Accept, override, or reject — never silently pass.** Ambiguous data is escalated to a human, never guessed.
7. **One pattern, applied consistently.** The same gate mechanic, audit trail, and mental model everywhere.
8. **Recovery is first-class.** Every failure state has a resubmit path. Pick up from the point of failure with corrected data — never a full restart.
9. **The audit trail is the source of truth.** Not logs, not memory — the recorded state of every decision, input, and transition.
10. **Make the right path the easiest path.** Clear requirements upfront, clear errors on failure.
11. **Every data point carries its provenance.** How data was obtained determines how it is trusted, displayed, and governed.
12. **Authority, data certainty, and outcome certainty are independent** and tracked separately.
13. **Human overrides are always flagged** — regardless of the overriding user's authority. Flagging is governance, not a quality judgement.
14. **Data has its own lineage,** separate from the workflow audit trail.
15. **Originals are never erased.** New assertions layer over old ones; the prior value is preserved.
16. **Conflict resolution is a governed human decision.** When sources conflict, the Platform detects it, presents both with provenance, and routes to the right authority. The losing value is retained.

---

## 6. Design System

### 6.1 Colour palette

| Token | Hex | Usage |
|---|---|---|
| Brand Navy | `#2E3264` | Primary accent, buttons, top bar, headings |
| Teal (interactive) | `#1A8070` | Links, interactive text, active states |
| Teal (decorative) | `#2BA692` | Decorative only |
| Teal Light | `#E8F7F5` | Backgrounds, callout boxes, chips |
| Charcoal | `#383F47` | Body text |
| Mid Grey | `#636A72` | Secondary text |
| Light Grey | `#DCDCDC` | Borders, dividers |
| Amber (text / bg) | `#854F0B` / `#FAEEDA` | Warnings, "needs work" states |
| Success Green | `#1A8070` family | Confirmation, completed states |
| Error Red | `#A32D2D` / `#FCEBEB` | Errors, failures, destructive actions |

### 6.2 Typography

- **Typeface:** Plus Jakarta Sans.
- **Body:** 16px, regular, 1.5 line height, Charcoal.
- **Headings:** Brand Navy. Scale: H1 28px / H2 22px / H3 18px / H4 16px, semibold.
- **Captions / metadata:** 13px, Mid Grey.
- **Monospace:** for IDs, signal names, JSON — a standard mono stack.

### 6.3 Layout & spacing

- 8px spacing grid.
- Page max content width ~1280px; full-bleed for the canvas.
- Side panels: 320px fixed width, slide in from the right.
- Cards: 8px radius, 1px Light Grey border, subtle shadow on hover.

### 6.4 Environment tags

Each environment has a fixed colour identity, used on the environment indicator, tags, and badges.

| Environment | Dot | Fill | Border | Text |
|---|---|---|---|---|
| Dev / Sandbox | `#534AB7` | `#EEEDFE` | `#AFA9EC` | `#26215C` |
| SIT | `#185FA5` | `#E6F1FB` | `#85B7EB` | `#042C53` |
| UAT | `#854F0B` | `#FAEEDA` | `#EF9F27` | `#412402` |
| Prod | `#A32D2D` | `#FCEBEB` | `#F09595` | `#501313` |

### 6.5 Core components

- **Buttons:** Primary (navy fill), Secondary (navy outline), Tertiary (text only), Destructive (red). 36px height, 8px radius.
- **Status badges:** pill-shaped, colour-coded by status family. Always paired with a human-readable label.
- **Chips / tags:** for signals, environments, versions, roles.
- **Side panel:** header (title + close), scrollable body, sticky footer for actions.
- **Inline confirmation:** destructive and irreversible actions confirm *inline* (a confirm/cancel pair replacing the trigger). **Never a modal `confirm()` dialog.**
- **Toasts:** transient success/error feedback, top-right, auto-dismiss.
- **Empty states:** every list and panel has a designed empty state with a one-line explanation and a primary call to action.
- **Loading states:** skeleton placeholders for content regions; inline spinners for actions.
- **Provenance pill:** a small coloured chip on a data value indicating its provenance — teal for system/AI-authored, amber for human override.

### 6.6 Interaction rules

- **One action = one outcome.** The frontend never orchestrates multi-step logic or sequential calls for a single user action; the backend owns state machines.
- **The frontend renders and captures input only.** It never decides status, never retries, never compensates for errors.
- **Optimistic feedback** where safe; immediate visible state change on every interaction.
- **Auto-save** for authoring surfaces (agents, canvas), debounced, with a clear save-state indicator ("Saving…", "Saved", "Unsaved changes").

---

## 7. Domain Model

### 7.1 Entity relationships (conceptual)

```
Organisation
 ├─ Users (roles)
 ├─ Environments (Dev → SIT → UAT → Prod)
 ├─ Workspaces
 │   ├─ Agents ──< Agent Versions
 │   └─ Workflow Definitions ──< Workflow Definition Versions
 ├─ Provider Accounts ──> AI Providers (catalogue)
 ├─ Model Configurations ──> Model Versions (catalogue)
 ├─ Governance Policies / Taps
 └─ Integrations (Webhooks, API connections)

Workflow Run
 ├─ belongs to a Workflow Definition Version (pinned)
 ├─ Step Runs ──> Signals (produced/consumed)
 ├─ Gates ──> Gate Actions
 └─ Case
     └─ Data Points ──< Assertions (provenance-tracked)

Audit Record — emitted for every consequential event
```

### 7.2 Agent — the five fields

Every agent is defined by exactly five fields, authored in this order:

1. **Name** — display name.
2. **Purpose** — one sentence, human-facing. Single-line, physically constrained. Shown on cards, canvas nodes, and in the Portal.
3. **Instructions** — the operating contract with the AI. Precise, operational. Multi-line.
4. **Acceptance Criteria** — testable conditions that prove the output met the purpose. A list of statements.
5. **Output** — the shape of a correct result: a description, an optional example output, and an optional uploaded template.

Agents are created from a single free-text **Job Description** the builder writes naturally; the Platform generates all five fields from it.

### 7.3 Workflow definition — shape

A workflow definition contains:

- **Steps** — ordered list of agent / gate / merge nodes, each with a position for canvas rendering.
- **Edges** — connections between steps, optionally carrying **signal mapping rules** (rename a producer's signal to a consumer's expected name) and an **override signal**.
- **Entity block** — `{ type, identity_signal }` — defines the Case this workflow governs.
- **Output Contract** — see §7.5.
- **Initial inputs** — the inputs a requester must provide to start a run.
- **Portal visibility** — whether requesters can start this workflow themselves.

### 7.4 Status lifecycles

| Object | States |
|---|---|
| Agent | `draft → review → needs_work → review → ready → promoted` |
| Workflow Definition | `draft → published` (published versions are immutable) |
| Workflow Run | `pending_intake_review → pending → running → paused_at_gate → awaiting_caller_input → completed / failed / cancelled` |
| Gate | `open → actioned / bypassed / timed_out / declined` |
| Review Task | `pending → in_review → needs_work → completed / recalled` |

### 7.5 Output contract

The output contract declares how a workflow's result is presented to the requester.

```json
{
  "render_mode": "structured | document | markdown | json",
  "title": "Project initiation record",
  "portal_visible": true,
  "entity": { "type": "project", "identity_signal": "project_name" },
  "initial_inputs": [
    { "signal": "project_brief", "label": "Project brief", "format": "text" }
  ],
  "fields": [
    {
      "signal": "risk_level",
      "label": "Risk level",
      "format": "text",
      "group": "risk",
      "headline": true,
      "show_if": { "signal": "requires_escalation", "op": "truthy" }
    }
  ]
}
```

**Field formats:** `text`, `currency` (£ + thousands), `percentage` (1 dp + %), `count` (integer), `boolean` (Yes/No), `list` (bulleted), `duration_days`, `date` (DD Mon YYYY), `markdown`.

**Conditional visibility (`show_if`):** evaluated client-side. Operators: `eq`, `neq`, `in`, `not_in`, `truthy`. A field with an unsatisfied `show_if` is hidden.

---

## 8. Functional Modules

Each module below is specified with its purpose, screens, UI layout, interactions, and states.

---

### 8.1 Agent Builder

**Purpose:** Let a builder create a reusable AI agent from a plain-language description, test it, version it, and promote it.

#### Screens

**A. Agents list** (`/studio/agents`)
- Grid of agent cards. Each card: name, **purpose line** (visible without opening), status badge, current version, last-edited.
- Top bar: search, filter (status, workspace), sort, **+ New Agent** primary button.
- Empty state: "No agents yet. Create your first agent to get started."

**B. Agent Builder workspace** (`/studio/agents/:id`)

A single-page workspace — no wizard, no step transitions.

```
┌─────────────────────────────────────────────────────────────┐
│  ‹ Agents   Agent name        [v3 ▾] [● Ready] [Promote ▸]   │
├──────────────────────────────────────┬──────────────────────┤
│  JOB DESCRIPTION                      │  TEST PANEL           │
│  ┌────────────────────────────────┐  │                       │
│  │ Describe the job in plain      │  │  Input                │
│  │ language…                      │  │  ┌─────────────────┐  │
│  └────────────────────────────────┘  │  │                 │  │
│            [ Build artifact ]         │  └─────────────────┘  │
│                                       │      [ Run test ]     │
│  ─ GENERATED FIELDS ───────────────   │                       │
│  Name        [_______________]        │  Output               │
│  Purpose     [_______________]  1 line│  ┌─────────────────┐  │
│  Instructions                         │  │                 │  │
│  ┌────────────────────────────────┐  │  └─────────────────┘  │
│  │ multi-line editor              │  │                       │
│  └────────────────────────────────┘  │  Evaluation           │
│  Acceptance criteria                  │  ✓ Criterion 1  pass  │
│  • criterion ………………………… [×]          │  ✗ Criterion 2  fail  │
│  • [+ add criterion]                  │    → suggestion       │
│  Output                               │                       │
│  Description […]  Example […]  ⬆ Tmpl │  [ Apply & re-run ]   │
└──────────────────────────────────────┴──────────────────────┘
```

#### Behaviour

- **Job description → generation:** The builder writes the job naturally (no enforced format). On **Build artifact**, the Platform evaluates completeness. If something critical is missing, it surfaces *one* specific clarifying question; otherwise it generates all five fields immediately. Regenerate button is labelled **Rebuild**.
- **Five fields:** all editable after generation. Purpose is a single-line, physically constrained input. Instructions and Output description are multi-line. Acceptance criteria is an editable list (add / edit / remove rows).
- **Acceptance criteria absent:** warn and proceed — "No acceptance criteria defined — evaluation will be derived from your job description and output. Results may be less precise." Dismissible.
- **Test panel:** the builder enters a test input, runs it, sees the output and a per-criterion evaluation (pass / partial / fail, with evidence and a suggested fix for non-passes). **Apply & re-run** applies a suggestion and re-tests.
- **Auto-save:** every change saves a draft, debounced. Save-state indicator in the header.
- **Versioning:** the version dropdown lists named versions. Sending an agent for review snapshots a version automatically. Builders can also cut a named version explicitly.
- **Hotfix:** a promoted version can be hotfixed — this cuts a new draft from the promoted version, leaving the promoted version untouched until the hotfix itself is promoted.
- **Promote:** opens the promotion flow (§8.9).

#### States

- Empty (no job description), generating (skeleton on the five fields), generated, testing, evaluation-complete, error.

---

### 8.2 Workflow Canvas Builder

**Purpose:** Let a builder compose agents and gates into an executable workflow on a visual canvas.

#### Screen (`/studio/workflows/:id/canvas`)

A full-bleed canvas surface.

```
┌──────────────────────────────────────────────────────────────┐
│ ‹ Workflows  Workflow name   [⚙ Workflow settings] [● Saved]  │
│  [+ Add Agent] [+ Add Gate]                    [Publish ▸]    │
├───────────────────────────────────────────┬──────────────────┤
│                                            │  CONFIG PANEL    │
│   (●)──▶[ Agent: Intake ]──▶◇ Gate ──▶     │  (slides in on   │
│            │                    │          │   node click)    │
│            ▼                    ▼          │                  │
│        [ Agent ]──▶[▰ Merge ]──▶(●) End    │                  │
│                                            │                  │
│        · D3 zoom / pan canvas ·            │                  │
└───────────────────────────────────────────┴──────────────────┘
```

#### Node types

| Node | Shape / colour | Represents |
|---|---|---|
| **Start** | Circle | Initial inputs + portal visibility |
| **Agent** | Navy-header card; shows agent name + purpose + pinned version chip | An agent step |
| **Gate** | Coloured diamond (colour by gate type) | A human review gate |
| **Merge** | Amber rounded rectangle | Fan-in of parallel branches |
| **End** | Circle | Output contract render mode |

#### Edges

- Drawn as bezier connectors between nodes.
- **Signal mapping:** an edge can carry mapping rules that rename a producer's output signal to the name a consumer expects. Authored in the edge config panel.
- **Override signal:** an edge can override which signal drives routing. When set, an on-edge **pill** shows the override signal name (teal chip).
- Edges with no mapping render clean; the mechanism is visible only when used.

#### Config panel (right side)

Slides in on node or edge selection. Context-sensitive. **Mutually exclusive** — selecting a node, an edge, or opening workflow settings closes the others.

- **Agent node:** two tabs.
  - *Config* — agent picker (from the workspace), pinned version, executor type.
  - *Signals* — declare the agent's output signals (`name` + `type`: string / number / boolean). Used to wire the workflow.
- **Gate node:** gate type (7 selectable types — see below), trigger condition (signal + operator + threshold, with compound AND/OR), required role(s), signatory mode, available actions, decline-note requirement.
- **Merge node:** merge policy (read-only display of how inputs combine).
- **Edge:** routing (from/to, edge type), override signal (constrained dropdown of the target's declared signals + "custom"), and the **signal mapping rules** list (add / edit / remove source→target rule rows).
- **Backend state block:** a read-only section showing the resolved runtime state for the node (pinned version, gate config, etc.).

#### Workflow settings panel

Opened from the toolbar gear button (`⚙ Workflow settings`). Third state of the right-side panel slot. Authors the **workflow-level output contract**:

- Render mode (structured / document / markdown / json) + title.
- **Output fields list** — per-field rows: signal, label, format, group, headline flag, and a constrained **`show_if` picker** (dropdown of signals produced by workflow steps + initial inputs, plus an "always show" option).
- Initial inputs.

#### Behaviour

- **Auto-save**, debounced, with a save-state indicator. Layout-only changes (dragging a node) and structural changes (adding a node, wiring signals) save independently.
- **Gate types:** `escalation`, `confirmation`, `exception`, `feedback_loop_cap`, `conflict_resolution`, `structured_correction`, `approval`. Each renders with its own diamond colour.
- **Validation:** structural edits are validated before save. Validation errors surface in a dismissible banner with one row per error, each carrying a stable, human-readable error code (e.g. unknown signal reference, unreachable gate condition, duplicate step name, graph cycle without a feedback gate). Invalid drafts cannot be published.
- **Publish:** transitions the definition draft → published, creates an immutable published version, and makes the workflow runnable. Publishing re-validates.

#### States

- Empty canvas (start + end only), authoring, validation-error banner, saving, saved, publish-confirm.

---

### 8.3 Workflow Execution & Runtime

**Purpose:** Run a workflow against a request and surface its live state.

#### How a run works

1. A request enters via the Portal, the API, or an internal trigger.
2. **Intake** validates and scores the request (§8.6). An `intake_review` gate may fire.
3. The run is created and pinned to a specific published workflow version.
4. The engine executes steps in dependency order. Each agent step consumes its required input signals and produces output signals.
5. At a gate step, the run **pauses** (`paused_at_gate`) and a Gate is opened for a human.
6. If a step needs an input nobody has provided, the run can pause `awaiting_caller_input`.
7. The run ends `completed`, `failed`, or `cancelled`.

#### Screens

**A. Runs list** (`/studio/runs`)
- Table of runs: workflow, requester, status (human-readable), current step, started, duration.
- Filter chips: All / Active / Awaiting review / Completed / Failed.
- Scope is role-gated: builders/observers see their own or workspace runs; managers and admins see all organisation runs.

**B. Run detail** (`/studio/runs/:id`)

```
┌──────────────────────────────────────────────────────────────┐
│ ‹ Runs   Run #1234   [● Paused at gate]      [Cancel run]     │
├──────────────────────────────────────────────────────────────┤
│  PIPELINE                                                      │
│  (✓)──(✓)──(◇ open)──( )──( )      ← step-state strip          │
│                                                                │
│  STEPS                          │  SIGNALS                     │
│  ✓ Intake        completed      │  project_name   "Apollo"     │
│  ✓ Risk scoring  completed      │  risk_level     "High"  ⓘ    │
│  ◇ Review gate   open  →[Review]│  …                           │
│  · Resourcing    pending        │                              │
│                                 │  CERTAINTY PROFILE           │
│  OUTPUT (contract-rendered)     │  outcome certainty  0.82     │
│  …                              │  PROVENANCE  …               │
└──────────────────────────────────────────────────────────────┘
```

- **Pipeline strip:** compact node-state visualisation (completed / running / open gate / pending / failed).
- **Steps list:** each step with status, timing, and a link to its detail (inputs snapshot, output, model + version used).
- **Signals panel:** every signal value, each with a provenance indicator.
- **Output panel:** the result rendered per the output contract.
- **Certainty profile:** live outcome-certainty breakdown.
- **Cancel run:** inline-confirmed; allowed on non-terminal runs.

#### States

- Pending intake, running, paused at gate, awaiting caller input, completed, failed, cancelled.

---

### 8.4 Human-in-the-Loop Gates & Review

**Purpose:** The governance core. A gate is a defined pause where a human accepts, overrides, or rejects — never silently passes.

#### My Tasks (`/studio/tasks`)

- A list of gates assigned to the current user (and unassigned gates the user is eligible to action).
- Each row: workflow, run, gate type, opened-at, age, requester, a one-line context summary.
- Filter by gate type and age.

#### Gate Review screen (`/studio/runs/:id/gates/:gateId`)

```
┌──────────────────────────────────────────────────────────────┐
│  Review gate — Confirmation            Run #1234   ◷ 12m open │
├───────────────────────────────────────┬──────────────────────┤
│  CONTEXT                                │  SIGNATORIES         │
│  Pipeline so far: ✓ ✓ ✓ ◇              │  ☐ Manager           │
│  Headline outputs:                      │  ☑ Compliance        │
│   Risk level   High                     │  (multi-sig          │
│   Budget       £240,000                 │   scoreboard)        │
│                                         │                      │
│  Full record / chat-assisted summary    │  ASSIGN              │
│  ┌─────────────────────────────────┐   │  [ reassign ▾ ]      │
│  │ AI-assisted governance record   │   │                      │
│  └─────────────────────────────────┘   │                      │
│                                         │                      │
│  ACTIONS                                │                      │
│  [ Approve ] [ Reject ] [ Redirect ]    │                      │
│  [ Override value ] [ Request input ]   │                      │
│  [ Decline ]                            │                      │
└───────────────────────────────────────┴──────────────────────┘
```

#### Gate types and their actions

| Gate type | Purpose | Available actions |
|---|---|---|
| **Confirmation** | Confirm a result before proceeding. | approve, reject |
| **Approval** | Formal sign-off, often multi-signatory. | approve, reject |
| **Escalation** | Route a high-risk case to higher authority. | approve, reject, redirect |
| **Exception** | Handle an out-of-policy case. | override, reject |
| **Conflict resolution** | Two sources wrote conflicting values to one data point. | resolve_conflict |
| **Structured correction** | Reviewer corrects specific fields. | correction_applied |
| **Feedback loop cap** | Bound the number of feedback iterations. | approve, continue, stop |
| **Request for input** | A required input is missing. | input_provided |
| **Intake review** | The request failed intake checks. | accept, reject, override |

#### Gate action types

`approved`, `rejected`, `redirected`, `override_applied`, `correction_applied`, `input_provided`, `resubmit`, `declined`, `resolve_conflict`.

#### Key UX behaviours

- **Nothing passes silently.** Every gate forces an explicit decision.
- **Multi-signatory:** when a gate requires multiple roles, a **signatory scoreboard** shows who has signed and who is outstanding. The run proceeds only when the signatory rule is satisfied.
- **Conflict resolution gate:** renders both conflicting values side by side, each with full provenance. The reviewer picks A, B, or an override value, and **must** give a reason. The winner is written `is_current`; the loser is retained, linked, and `is_current=false`.
- **Structured correction gate:** renders an editable form of the named correctable fields.
- **AI-assisted record:** the gate can present an AI-generated governance summary of the run so far; the reviewer reads, edits, and confirms it as the governance record.
- **Assign / reassign:** a gate can be reassigned to another eligible user inline.
- **Decline note:** when a gate requires it, a decline cannot be submitted without a note.
- **Recovery:** rejecting or declining a gate produces a resubmit path — the run can be corrected and resumed from the failure point, never restarted.

---

### 8.5 Requester Portal

**Purpose:** Let non-technical requesters submit work into a workflow and track it — with zero exposure to pipeline internals.

#### Screens

**A. My Requests** (`/portal`)
- A list of the requester's submissions as cards.
- Filter chips: All / Active / Awaiting review / Complete / Failed.
- Each card: workflow title, a **human-readable status** (no internal state names), submitted date, last update.
- Empty state with a **New Request** call to action.

**B. New Request** (`/portal/new`)
- **Step 1 — Pick a workflow.** Only portal-visible, runnable workflows appear. Cards show title + purpose.
- **Step 2 — Intake form.** Generated from the workflow's `initial_inputs`. Each input renders with its label and format-appropriate control. Basic field-level validation (required, format).
- Submitting creates a run. If the workflow has an intake gate, the requester sees "Submitted — under review."
- A failed run offers **Resubmit** — the form pre-fills from the prior submission's provided values so the requester corrects rather than re-enters.

**C. Request detail** (`/portal/requests/:id`)
- The output, rendered per the output contract, polled live (~5s) while the run is non-terminal.
- **No pipeline internals.** No step names, no signals, no model details.
- While running: a friendly progress state. While awaiting input: a prompt for the missing input. On completion: the full contract-rendered output, grouped by `group`, with `headline` fields surfaced first.
- An **output standing** indicator: *authoritative* (all required inputs present) or *provisional* (completed with missing optional inputs).

---

### 8.6 Intake & Validation

**Purpose:** Every incoming request — from any channel — passes through intake before execution. Bad data is caught at the boundary.

#### Behaviour

1. An **Intake Record** is created before any execution.
2. **Profile calculation:** an *authority score* (from the source's configured authority) × a *certainty score* (declared at entry) → a quadrant.
3. **Contract validation:** Check 1 is structural (required inputs present, correctly typed); Check 2 is profile-based (does the request's authority/certainty profile meet the workflow's policy).
4. If checks fail or the profile demands it, an **`intake_review` gate** fires — a human accepts, rejects, or overrides.
5. Accepted requests proceed to a run; the run status moves `pending_intake_review → pending`.

#### UI

- Intake review surfaces in **My Tasks** as an `intake_review` gate.
- The gate shows the raw submission, the structural check results, and the computed authority/certainty profile.

---

### 8.7 Data Lineage & Provenance

**Purpose:** Every data point carries its full history across every run that touched it — a second audit trail, for *data* rather than *process*.

#### Concepts

- **Case** — the real-world entity (project, claim, invoice). Created or matched on run start by `{entity type + identity signal value}`. Auto-created; never blocks a run.
- **Data Point** — one logical field on a Case.
- **Assertion** — every value ever written to a Data Point, from any source, in any run. Assertion types: `initial`, `correction`, `re_extraction`, `human_override`, `re_assertion`, `conflict_resolution_winner`, `conflict_resolution_loser`.

#### Rules

- **Originals are never erased.** A new assertion layers over the old; the prior assertion is preserved and linked (`supersedes`).
- **Provenance** is recorded on every assertion: human override, system-injected, AI-extracted, or inferred.
- **Conflicts** between simultaneous sources are detected, surfaced at a conflict-resolution gate, and resolved by a human; both values are retained.
- **Certainty decay:** raw certainty + timestamp are stored; effective certainty is computed at read time using the source's decay profile (none / slow / medium / fast). No rows are updated as time passes.

#### UI

- **Provenance pills** on every rendered data value: teal = system/AI-authored, amber = human override.
- **Data point history:** clicking a value opens a timeline of every assertion — value, source, provenance, certainty, timestamp, and the run that produced it.
- **Lineage tiers:** *standard* (assertions recorded only for output-contract fields) or *full* (assertions for every signal in every run) — a per-workspace setting.

---

### 8.8 Model Ontology & Configuration

**Purpose:** Treat the AI model itself as a governed dependency with a lifecycle.

#### The four-layer model

1. **AI Provider** — a company operating inference endpoints (platform-curated catalogue).
2. **Provider Account** — the commercial relationship between an organisation and a provider: credentials, tier, entitled models. Can be *bring-your-own* (organisation holds the account) or *managed* (the Platform operator holds it and re-bills).
3. **Model Version** — a specific model release (platform-curated catalogue) with release date, deprecation date, successor reference, and capability type (text generation, image, speech, etc.).
4. **Model Configuration** — the operational binding: one model version + one provider account + runtime parameters (temperature, max tokens, timeout, retry policy). **Agents bind to one Model Configuration.**

#### Runtime resolution

At execution, the engine resolves: Agent → Model Configuration → Provider Account (credentials) + Model Version (capability) → Provider. The exact model and version are **stamped as provenance** on every step output.

#### UI (Admin)

- **Provider Accounts** — list, add (provider + credentials + ownership), test connection.
- **Model Configurations** — list, create (pick model version + provider account + parameters), grant to workspaces.
- **Model catalogue** — browse available model versions with deprecation warnings.

---

### 8.9 Environments & Promotions

**Purpose:** Move agents, workflows, and model configurations through pipeline stages under governance.

#### Environments

- Pipeline stages, organisation-scoped and **immutable** after onboarding (audit integrity). Default: Dev → SIT → UAT → Prod.
- Two anchors are fixed: **Sandbox/Dev** (authoring environment, entry point) and **Prod** (terminal).
- Each environment carries stage-appropriate governance defaults (permissive in Dev, strict in Prod).

#### Promotion

- Promotion is a **governed request**: a source environment nominates an object; the receiving environment evaluates and **accepts** or **rejects**.
- Each environment holds an **acceptance set** — the configurations explicitly accepted into it.
- A rejection records a mandatory reason.
- Every promotion event is audited.

#### UI

- **Promotion flow** — from an agent/workflow/model-config detail view: select target environment → submit → track request status.
- **Acceptance queue** — the receiving environment's pending promotions, with accept/reject actions (reject requires a reason).
- A **deprecation notice** is shown if a run is pinned to a deprecated version.

---

### 8.10 Governance Taps & Policy

**Purpose:** Apply governance checks automatically, without wiring them into the visible workflow.

#### Governance taps

- A **tap** is a governance check that fires at a trigger point — *before* a step, *after* a step, or *on a specific output signal*.
- Taps are configured at a **scope** (organisation or workspace), not drawn on the canvas.
- Each tap has a **loop mode** (how it behaves inside feedback loops: inform / cap / block) and a **failure policy**.
- When a tap fires, it runs a governance agent and records the result; a `block` outcome can stop the step.
- Every tap invocation is audited, with a per-step **governance trail** aggregating all taps that fired.

#### Governance artefacts & policy (the Evaluation surface)

Governance standards are **evaluated against agent output**, not injected into the agent's prompt — stronger governance, because it independently checks the output rather than trusting the agent to have followed a policy.

Governance artefacts (versioned, first-class):

- **Brand voice policy** — tone and style standards.
- **Data handling policy** — what may appear in outputs, PII rules.
- **Domain compliance rules** — regulatory requirements.
- **Prompting best-practice rubric** — standards for well-formed agent instructions.
- **Guardrail library** — reusable named checks with failure behaviour (warn / block / escalate).

These inherit **additively** down a hierarchy: Platform → Organisation → Workspace → Agent. Nothing defined at a level can be turned off below it.

#### UI

- **Governance** / **Evaluation** section: manage governance artefacts, the guardrail library, and scope-level taps.
- A tap configuration panel: trigger point, governance agent, loop mode, failure policy, rationale.

---

### 8.11 Quality & Evaluation Framework

**Purpose:** Independently assess agent output against criteria, with full isolation.

#### The isolated evaluator

- A separate AI call with its **own context window**. It never sees the agent's instructions or reasoning — only the criterion being evaluated and the output being tested.
- It evaluates two streams: the agent's **acceptance criteria** and the inherited **governance artefacts**.
- Per-criterion result:

```json
{
  "verdict": "pass | fail | partial",
  "score": 0.0,
  "evidence": "what in the output supports this verdict",
  "suggestion": "specific improvement, or null if pass"
}
```

#### Triggers

- On every test run in the Agent Builder.
- At promotion — a full evaluation must pass before an agent can be promoted.

#### UI

- Evaluation results render in the Agent Builder test panel: a per-criterion list (pass / partial / fail) with evidence and suggestions, marked by source (acceptance criterion vs governance artefact).
- An override requires Reviewer role and a note.

---

### 8.12 Trials — Authoring-Time Variant Testing *(roadmap / v2)*

**Purpose:** Run authored variants in parallel under real conditions, gather evidence over a window, and make a governed pin decision.

- **Model Trials** — hold the agent constant, vary the Model Configuration across 2..N arms.
- **Agent Trials** — hold the model constant, vary the agent's authored content across versions.
- **Modes:** *Shadow* (challengers run in parallel but their output is captured, not delivered) and *Live* (all arms serve real traffic, fully governed).
- Arm assignment is decided by the Platform, never by the caller.
- Feedback is aggregated **per arm**. The winning variant is **pinned by a governed decision** (builder + reviewer co-sign). Losing arms are preserved in version history with trial attribution.

#### UI

- **Trials** section: create a trial (subject, arms, mode, window), monitor per-arm metrics, adjudicate, and pin the winner.

---

### 8.13 Notifications

**Purpose:** Tell the right people about gates, completions, and failures, without noise.

- Events: `gate.opened`, `gate.actioned`, `run.completed`, `run.failed`, and review-task assignment.
- Channels: in-app (always on) and email; the channel list is extensible (Slack/Teams as future adapters).
- **Magic links:** email notifications can carry a single-use link that deep-links straight to the relevant gate or run.
- **Per-user preferences:** users choose which events reach which channels. In-app cannot be disabled.

#### UI

- A **notifications bell** in the top bar with an unread count and a dropdown of recent items.
- A **notification preferences** page (per-user, in Settings): a matrix of event × channel.

---

### 8.14 Integrations

**Purpose:** Connect external systems in and out.

#### Inbound — programmatic triggers

- A versioned REST API lets external applications trigger workflows: `POST /runs` with a workflow slug, inputs, an optional callback URL, a priority, and an idempotency key (same key within 24h returns the existing run). Returns a run id and a poll URL.
- Polling returns run status, the current gate (if any) with headline outputs, the output (when complete), output standing, missing inputs, certainty, and any error.
- An external caller can answer a `request_for_input` gate by providing inputs; approve/override/decline remain human and stay in the Platform UI.
- An MCP server exposes production workflows as callable tools for AI assistants.

#### Outbound — webhooks

- Registrable webhooks fire on `gate.opened`, `gate.actioned`, `run.completed`, `run.failed`.
- HMAC-signed payloads. Retry schedule: initial attempt + 3 retries at 30s / 5min / 30min.

#### UI (`/studio/integrations`)

- **Webhooks tab:** list, create (name, URL, workspace, events), deactivate, rotate secret, and an expandable **delivery log** per webhook (recent deliveries, status, retries).
- **Connections tab:** list API connections, create one (name + workspace) — the API key is shown **once** in a copy-to-clipboard banner — deactivate.

---

### 8.15 Audit Trail

**Purpose:** The single source of truth. Every consequential event is recorded.

- An **Audit Record** is emitted for: workflow publish, run start/complete/fail, gate open/action, promotions (initiated / passed / rejected / sent back), governance tap invocations, step entry, and more.
- Each record carries: action, actor (user or system), resource type + id, trigger, timestamp, and a structured detail payload.

#### UI (`/studio/audit`)

- A searchable, filterable table: filter by action, actor, resource type, date range.
- Each row expands to show the full detail payload.
- Cross-links from any run, gate, agent, or promotion to its audit records.

---

### 8.16 Admin & Settings

**Purpose:** Configure the organisation.

#### Admin (`/studio/admin`) — Org Admin and above

- **Users** — list, invite, assign roles, assign environment access, deactivate.
- **Environments** — view the pipeline (immutable), per-environment governance defaults.
- **Model Configurations & Provider Accounts** — §8.8.
- **Governance** — §8.10.
- **Organisation settings** — name, branding, defaults.
- **Email (SMTP)** — configure the outbound mail server. The password field shows a masked sentinel when set and preserves the stored value if unchanged.

#### User settings (all users)

- Profile, password.
- **Notification preferences** — §8.13.

---

## 9. Key User Journeys

### 9.1 Builder creates and ships an agent

1. Builder opens **Agents → New Agent**.
2. Writes a plain-language job description, clicks **Build artifact**.
3. The Platform generates the five fields (or asks one clarifying question first).
4. Builder refines the fields, tests in the right panel, reviews per-criterion evaluation, applies suggestions.
5. Builder sends the agent for review → a version is snapshotted, a review task is created.
6. A Reviewer actions the review task; on pass, the agent reaches **Ready**.
7. Builder promotes the agent to the next environment; the receiving environment accepts it.

### 9.2 Builder composes and publishes a workflow

1. Builder opens **Workflows → New Workflow**, lands on the canvas.
2. Adds agent nodes (picking agents + pinned versions), gate nodes, and a merge if needed.
3. Wires signals between steps; adds mapping rules on edges where names differ.
4. Opens **Workflow settings**, authors the output contract (fields, formats, `show_if`).
5. Sets initial inputs and portal visibility on the Start node.
6. Resolves any validation errors in the banner.
7. Clicks **Publish** — an immutable version is created; the workflow is runnable.

### 9.3 Requester submits and tracks a request

1. Requester opens the **Portal → New Request**.
2. Picks a portal-visible workflow; fills the generated intake form.
3. Submits — a run is created; intake validates and scores it.
4. Requester watches the request detail page; status updates in plain language.
5. If a gate fires, reviewers are notified and action it.
6. On completion, the requester sees the contract-rendered output, marked authoritative or provisional.
7. If the run failed, the requester clicks **Resubmit** — the form pre-fills with their prior inputs to correct.

### 9.4 Reviewer actions a gate

1. Reviewer gets an in-app + email notification; the email carries a magic link.
2. Opens the Gate Review screen: context, pipeline-so-far, headline outputs, AI-assisted record.
3. For a confirmation gate: approves or rejects. For a conflict gate: picks a value with a mandatory reason. For a structured-correction gate: edits the named fields.
4. If multi-signatory: the scoreboard updates; the run proceeds only when the signatory rule is met.
5. The gate action is audited; the run resumes or recovers.

### 9.5 Promoting a model configuration

1. Admin creates a Model Configuration in Dev and grants it to a workspace.
2. Admin promotes it toward SIT.
3. The SIT acceptance queue shows the pending promotion; an authority accepts (or rejects with a reason).
4. The configuration joins SIT's acceptance set and becomes resolvable for runs there.

---

## 10. Cross-Cutting UX Requirements

- **Human-readable status everywhere.** Internal state machine names never reach requesters; builders see them only where useful, always paired with a plain label.
- **Provenance is always visible** on data values, never hidden behind a click-only affordance.
- **Irreversible actions are marked and inline-confirmed** — publishing, promoting, cancelling a run, rotating a secret, deactivating a user.
- **Every list and panel has a designed empty state.**
- **Every failure has a recovery path.** Resubmit, not restart.
- **Loading is never a blank screen** — skeletons for content, inline spinners for actions.
- **Auto-save on all authoring surfaces** with an explicit, always-visible save-state indicator.
- **Role-aware UI** — actions the user cannot perform are hidden or disabled with a tooltip reason; navigation items are role-gated.
- **The environment is always visible** via the top-bar indicator; its colour identity is consistent everywhere.

---

## 11. Non-Functional Requirements

### 11.1 Multi-tenancy & data isolation

- A platform-level store holds organisations, users, access control, audit, credentials, and platform configuration.
- Each customer organisation's operational data (workflows, runs, cases, intake records, gates) lives in an **isolated per-organisation store**.
- Every tenant-scoped query is filtered by organisation; by-id lookups are never trusted without the tenant filter.

### 11.2 Security

- Authentication with session tokens held in HttpOnly cookies.
- Role-based authorisation enforced server-side at every endpoint.
- Credentials and secrets encrypted at rest.
- HTTPS-only; CORS restricted to an explicit allowlist; standard security headers (HSTS, X-Frame-Options, CSP).
- Rate limiting on authentication endpoints.
- Webhook payloads HMAC-signed; webhook URLs HTTPS-only.
- Single-use, expiring magic-link tokens.
- Roadmap: SSO (OIDC/SAML), SCIM provisioning — the Platform as a relying party inheriting the enterprise identity provider.

### 11.3 Architecture

- **Backend:** a Python web service (FastAPI-style), relational database (SQLite for local development, PostgreSQL in production), ORM-managed schema.
- **Frontend:** a React single-page application (Vite build). All API calls use relative URLs.
- **AI runtime:** pluggable AI providers behind a single resolution interface; a self-hosted model option is supported. Provider executors are added behind one consistent router.
- **Background work:** a job queue for retries, sweeps, and scheduled work.
- **Frontend/backend boundary (hard rule):** one user action maps to one backend call. The frontend renders and captures input only — it never decides status, never sequences calls for a single outcome, never retries or compensates. The backend owns every state machine.

### 11.4 Datetime & formatting

- All timestamps are stored and transmitted in UTC, ISO-8601.
- The UI localises display (e.g. DD Mon YYYY) but never sends locale-specific datetimes.

### 11.5 Auditability & immutability

- Published workflow versions and named agent versions are **immutable**.
- Audit records are append-only.
- Data assertions are append-only; superseded values are preserved and linked.
- Environments are immutable post-onboarding to preserve audit integrity.

### 11.6 Performance & scale targets

- Run detail and gate screens render in under 1s for typical runs.
- The Portal request detail polls at ~5s while a run is non-terminal and stops on terminal state.
- The canvas remains smooth (60fps pan/zoom) for workflows up to ~50 nodes.
- Background sweeps (webhook retries, intake expiry) run on a fixed cadence without blocking request paths.

---

## 12. Visual & Interaction Reference Summary

| Element | Specification |
|---|---|
| Primary action button | Navy fill `#2E3264`, white text, 8px radius, 36px height |
| Links / interactive text | Teal `#1A8070` |
| Headings | Navy `#2E3264`, Plus Jakarta Sans semibold |
| Body text | Charcoal `#383F47`, 16px, 1.5 line height |
| Warning / needs-work | Amber text `#854F0B` on `#FAEEDA` |
| Error / destructive | Red `#A32D2D` on `#FCEBEB` |
| Side panel | 320px, slide-in from right, header + scroll body + sticky footer |
| Confirmation | Inline confirm/cancel pair — never a browser dialog |
| Provenance pill | Teal = system/AI authored; Amber = human override |
| Environment tag | Per-environment colour set (Dev violet, SIT blue, UAT amber, Prod red) |
| Save indicator | "Unsaved changes" → "Saving…" → "Saved", visible in the surface header |
| Empty state | Illustration-light, one-line explanation, one primary CTA |

---

## 13. Build Scope Guidance

If building incrementally, this is a sensible order:

1. **Foundation** — organisations, users, roles, environments, auth, the platform/tenant data split.
2. **Model ontology** — providers, accounts, model versions, configurations, runtime resolution.
3. **Agents** — the Agent Builder, the five-field model, versioning, the test panel.
4. **Workflow authoring** — the canvas, node/edge model, signal wiring, output contract, publish.
5. **Execution engine** — runs, steps, signals, the run detail screen.
6. **Gates & review** — gate types, the Gate Review screen, My Tasks, multi-signatory, recovery.
7. **Intake** — validation, scoring, the intake-review gate.
8. **Portal** — request submission, tracking, contract-rendered output.
9. **Provenance & lineage** — cases, data points, assertions, provenance pills, conflict resolution.
10. **Governance** — taps, governance artefacts, the isolated evaluator.
11. **Promotions** — environment acceptance sets, the promotion flow.
12. **Notifications, webhooks, the API, the audit viewer.**
13. **Trials** *(v2)*.

Earlier stages unblock later ones: nothing is runnable without authoring (4) and execution (5); governance (6, 9, 10) is what makes the product the *governed* platform rather than just an automation tool.

---

*End of specification.*
