# Product Methodology

What the Padhanam platform encodes for its users.

This document is distinct from `charter/methodology.md`. The methodology document covers how Padhanam itself is built (start simple, refactor often; framing-prompt-as-recommendation; structural-promotion threshold). This document covers what the platform's agent layer encodes for the professional functions it demonstrates against.

## The core commitment

Methodology is embedded, not gated. Defaults encode the right thing for the chosen methodology; overrides at decision points are cheap and non-punitive. Methodology activates at decision points, not as workflow gates. Old enterprise SaaS treats the methodology as the product's wireframe and makes the user traverse it; this platform inverts that, treating user intent as primary and methodology as the smart default that the user can override without friction.

See `charter/principles.md` for the architectural commitment that backs this surface; see `charter/bet.md` for the strategic positioning.

## Functional domains

Four professional functions the platform demonstrates against. Methodology selection per domain is a selection space at this stage; per-domain methodology decisions land as each domain enters package scope.

### Product Management

Stage-specific methodologies (selected per product lifecycle phase):

- PoC: Lean Startup, Customer Development, Jobs to be Done, Google Ventures Design Sprint.
- Prototyping: Design Thinking, Double Diamond, Lean UX, Design Sprint.
- Enterprise-grade products: Stage-Gate, Pragmatic Institute framework, SAFe Lean Portfolio Management.

Cross-cutting methodologies (selected independently, applied across stages):

- Strategy: Lean Value Tree, North Star Framework, OKRs, Wardley Mapping.
- Prioritisation and validation: Kano, RICE, MoSCoW, ICE, Opportunity Solution Tree.

### Marketing

1. Marketing Audit: Kotler's Marketing Audit Framework, SOSTAC, Forrester Marketing Maturity Model.
2. Content Generation: StoryBrand, Content Marketing Institute pillar-and-cluster, AIDA, PAS, BAB, buyer journey mapping (TOFU, MOFU, BOFU), Nielsen Norman tone-of-voice dimensions.
3. Product Launch and Go-to-Market: April Dunford positioning, Pragmatic Marketing launch model, Product Marketing Alliance launch tiering.
4. Customer Advocacy and Reference Programs: Forrester reference program model, advocate tiering, case study narrative structures.
5. Account-Based Marketing: ITSMA tiered model (1:1, 1:few, 1:many), Forrester ABM framework, Demandbase playbooks.

### Learning and Development

1. Learning Design: ADDIE, SAM, Action Mapping, 70-20-10.
2. Knowledge Management: SECI, Knowledge-Centered Service, Communities of Practice.
3. Content Creation and Curation: Bloom's Taxonomy, Mayer's principles of multimedia learning, microlearning frameworks, Search-Sense-Share curation.
4. Learning Analytics and Measurement: Kirkpatrick's Four Levels, Phillips ROI Methodology, Brinkerhoff Success Case Method.
5. Audit: ISO 30414, Brandon Hall maturity framework, ATD Capability Model.

### Project and Programme Management

Four delivery methodology options that cascade through every sub-workflow:

- PRINCE2.
- Waterfall.
- Agile (Scrum, Kanban).
- SAFe.

Sub-workflows that inherit the chosen methodology: planning and scoping, execution and tracking, governance and reporting, risk and change management, stakeholder communication.

## Methodology shape diversity

The methodologies in the lists above are not all the same architectural shape, and the diversity is intentional. Stage-Gate is a process methodology with gates and phase reviews; ADDIE is a sequence; Kano is a classification model; AIDA is a copywriting structure; SECI is a knowledge-creation cycle; April Dunford positioning is a worksheet shape; ABM tiering is a customer-segmentation rubric. These embed differently in the product. An agent that defaults to Lean Value Tree shapes its planning. An agent that defaults to AIDA shapes its outputs. The implementation pattern per methodology shape is part of what the demonstration surfaces and is settled per domain as the domain enters package scope.

## Build sequence

1. **Product Management** first. Operator's deepest expertise; senior product leaders are the primary audience; demonstration value is highest.
2. **Learning and Development and Marketing** next. Operator has direct user access in both domains for validation, which is the surface that exposes whether methodology embedding works in practice.
3. **Project and Programme Management** last. PgM remains a live burden for enterprise customers, and an AI workflow that surfaces senior-stakeholder visibility as new issues and risks emerge is a category-shifting capability. PgM is also the hardest test of the methodology-embedded-not-gated commitment, because procedural methodologies resist embedding without becoming gates. The order places it last so prior domains accumulate the embedding-pattern discipline before the hardest test runs.

## Selection discipline

Methodology selection within each domain stays as a selection space at this stage. Pre-committing to specific methodologies before consumer evidence drives the choice is the same shape of overreach the architecture rejected for the within-tenant segmentation primitive. Per-domain methodology decisions land as each domain enters package scope, with the consumer-evidence-needed posture per the methodology document. The selection space documented above is the candidate set; the active set is whatever the package-scoped framing settles on.
