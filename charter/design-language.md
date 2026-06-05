# Padhanam Design Language

De-personalised specification of the design decisions settled across the UI track. This is the single durable record. The mocks illustrate it; this document is the source of truth. Its home is the charter (alongside `charter/brand/tokens.css`), read by both strategic conversations and build sessions. It records design language, not committed feature decisions; where a design choice rests on a charter decision, the D-number is cited.

---

## 1. Foundations

The product is two views of one graph for a senior leader's whole life, work and personal, with no scope boundary (D156). The design language serves that: one visual system holds both domains, and domain is a property of an item, never a separate skin.

**Type is constant across domains.** Font, sizes, weights, and text colour do not change between work and personal items. A personal item and a work item read at the same typographic weight. Only colour, icon, and initials carry domain. This is load-bearing: varying type by domain would imply a hierarchy between work and life that the product explicitly rejects.

**Palette.** Plus Jakarta Sans throughout. Ink and warm-neutral surfaces in light and dark. Navy (`#2e3264`) is the brand and primary-action colour. Teal (`#1a8070`) is reserved for interactive and active states only. Semantic status: on-track green, needs-you violet, behind amber, at-risk red, done grey. Tier: warm (`#b0997e`) for personal, cool (`#7a8190`) for work. Dark-mode variants are muted, never neon. Spacing on a 4px grid; radii 6 to 10px; hairlines 0.5 to 1px.

**Teal is interactive-only.** Status that happens to be positive (on-track, done) uses its semantic colour, not teal. Teal signals "you can act on this," nothing else. This keeps the click-affordance signal clean across a dense surface.

---

## 2. The three-channel identity rule

An item is identified by three independent visual channels, each carrying one thing:

- **Icon = category.** Work, health, family, friends each have a fixed glyph. Category is the most stable property, so it gets the most stable channel.
- **Initials = specific context.** The named cluster an item belongs to (a client, a project, an event) shows as initials.
- **Colour = tier in lists, status in the week matrix.** In a list, colour encodes tier or domain. In the week matrix, the lane already encodes tier, so colour is freed to encode status instead.

The matrix exception is the rule's proof: a channel is assigned to whatever the surrounding structure does not already convey. Never duplicate a signal across two channels.

**Status pills are shared across domains.** A personal item and a work item use the same pill vocabulary and the same colours. Status is universal; only its subject differs.

---

## 3. Motion and surfaces

**The item drawer** is fixed to the right, roughly 420px wide (the conversation cell runs slightly wider, to about 470px, for a readable thread). It opens over a dimmed backdrop and slides in over 220ms on `cubic-bezier(0.16, 1, 0.3, 1)`. Motion is fast and quiet. Ambient or decorative motion is rejected; movement exists to show where something came from, not to entertain.

**The theme toggle uses the target-state convention.** In light mode it shows a moon, because the moon names the action (go dark); in dark mode it shows a sun. A tooltip states the action in words. This convention is standard across every surface.

---

## 4. The graph is the model

Every primary surface renders one underlying Causal Decision Diagram (D156): factor nodes typed lever, intermediate, or outcome, joined by directed causal edges, with qualitative status that ripples along them. There are no edge weights at this stage; the ripple is worst-status propagation, not probability.

The today list, the week matrix, and the dashboard are three renderings of that one graph, not three separate data models. A workspace is a lens over the graph, a named cluster of related nodes, never a silo. Tenancy stays database-per-tenant beneath the lenses.

A workspace offers a **Map and a Flow** view of the same nodes. The Map is the causal structure, levers feeding factors feeding outcomes. The Flow is the execution sequence. Editing a step in the Flow ripples derived status up the Map. A lever on the Map deep-links to its step in the Flow to edit it.

Output is recommendation-shaped, not chart-shaped (D9). The dashboard answers "how am I doing" with a verdict, a cause, and the move that changes it, not a wall of metrics.

---

## 5. Prioritisation

Ordering is **hybrid**: the system proposes a priority order, and the user overrides it by dragging, bumping, pinning a slot, or parking an item. Overrides ripple through the rest of the order. The system stays quiet, but it flags when an override mis-sequences or buries a dependency: an amber sequence warning when a blocker drops below what it blocks, a red park warning when a lever is genuinely buried. Pin locks an item in its current slot rather than forcing it to the top; a re-rank re-proposes the system order while honouring pins.

The principle: the system advises, the user decides, and the system speaks up only when a decision breaks a causal dependency.

---

## 6. Time windows

Two kinds of window, distinguished honestly in the controls. **Rolling** windows (7 days, 10 days, a custom day count) count forward from today and need no anchor. **Fixed** windows (100 days, a quarter, a custom span) begin on a user-set start date, and today sits wherever it actually falls inside them, marked, not at the left edge. A quarter runs three calendar months from its start, so a fiscal year that does not match the calendar still works. Long windows bucket by week, with a count and a worst-status colour per bucket; short windows show day columns.

---

## 7. The conversation cell

Chat lives inside the item drawer as a per-item **conversation cell**, scoped to one focus item (D115, D131, D158). It is not a global chatbot. A separate global routing input is the "talk from anywhere" entry point that resolves to the right item.

Within a cell, the assistant answers from the focus item and its causal neighbours, leads with the recommendation, and cites what it held in scope as source-typed chips (D131, D138). It asks rather than guesses when a reference is ambiguous (no-silent-operation, D139). It surfaces any write or communication action before taking it; a draft is saved, not sent. The thread is the substrate; the cell holds no state between turns (stateless-per-turn, D115).

Referencing another item from inside a cell is parked: the likely shape is an @-mention resolving to a link chip with a back-stack, but the mechanic is undecided and surfaced only as an affordance.

---

## 8. Journal

The journal is seeded by the day's record: it offers the day's items as starting points. The user writes their own words. The assistant never drafts an entry. There are no hard streaks and no guilt mechanics. The journal's warmth is opt-in and earned, never coerced.

---

## 9. Settings posture

**Model.** The provider row settles two things, where data goes and who bills; the specific model settles capability and cost. The model selector defaults to Auto, letting the provider route its own models, because most users should delegate that choice; a specific model is the opt-in. A local model is the private default (local-first). Billing splits into Padhanam-managed, where Padhanam meters and a real monthly ceiling belongs, and bring-your-own-key, where the provider bills and Padhanam imposes no cap; under a user's own key the only optional control is a behaviour guardrail, off by default, that can pause or fall back to local before the provider's own limit. Per-task routing is an advanced option.

**Privacy.** A data-residency control reflects jurisdiction (D12) over a dedicated per-tenant database (D32). Encryption is on, and the page commits the personal causal graph to per-tenant isolation and encryption, which is the posture that resolves the still-open charter decision on personal-graph isolation. The sensitive-data boundary is user-configurable, not a fixed list: the user picks which categories stay on-device and local-only, the set follows their own categories and extends, and any single workspace or item can be marked sensitive. Intake retention and reasoning-trace retention are explicit. Export and a two-step clean wipe span every store: database, causal graph, and traces.

**Connections.** The page is login-aware: services under the signed-in identity (Google) connect in one tap, others take a full sign-in. Intake is read-only and says so plainly (`calendar.readonly`, `gmail.readonly`, D148/D151); the product reads, it does not write or send. A connected calendar carries a domain tag (work, personal, family) set when the calendar is included, and its events inherit it; the tag is how the Today surface types a calendar-sourced item by domain (D159). At single-calendar scale the tag is one connection-level default surfaced read-only in the manage panel; per-calendar tags and their management become live when a second calendar with a distinct domain connects (the two-threshold rule). Retention lives on the Privacy page, not here. A custom-integration path recommends MCP, where one URL and a self-describing server need no protocol literacy, and demotes a plain REST endpoint to an advanced fallback. Authentication leads with reusing the user's current sign-in (SSO) as the recommended default, generalising the one-tap identity-reuse idea to the enterprise identity provider; fresh OAuth, an API key, or none are the fallbacks.

---

## 10. Cross-cutting principles

These recur across every surface and are the spine of the language.

- **Recommend, do not present a neutral menu.** Auto model routing, MCP-first custom connection, SSO-first authentication, the proposed priority order: each surface leads with a recommended default and makes the alternatives opt-in.
- **Reuse the identity the user already has.** Google one-tap and SSO-reuse are the same move; ask for a new credential only when the source sits outside the existing identity.
- **Read-only by default.** Intake reads, it does not write. A write or send crosses into explicit per-action confirmation (the high-classification pathway), never automatic.
- **Private by default.** The local model is the default engine; the sensitive boundary defaults on for personal categories.
- **Honest about data location.** The model choice states where prompts go, connections badge read-only, and the wipe names every store it clears.
- **Recommendation-shaped, not chart-shaped** (D9). Surfaces answer with the move, its cause, and what it affects, not with raw metrics.

---

## 11. References

Charter: D156 (the whole-life causal daily driver), D157 (the first slice), D158 (the live conversation cell), D159 (calendar items in the Today surface + the Connections page; calendar-to-domain mapping), D9 (recommendation-shaped output), D115 (ConversationFlow, stateless-per-turn), D131 / D138 (citation discipline), D139 / D134 (clarification; no-silent-operation), D148 / D151 (read-only calendar and email intake), D12 (tenant + jurisdiction), D32 (database-per-tenant), and the open deferred decision on personal causal-graph isolation and encryption. Tokens: `charter/brand/tokens.css`.
