# Brand Guidelines

The live brand specification Padhanam uses across charter artefacts, the platform UI, the deck, and any future surface. Maintained as a charter artefact per the same cadence as the PRFAQ and the methodology document.

The brand is Padhanam's going forward.

## Colours

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-brand-navy` | `#2E3264` | Primary accent, buttons, topbar, headings |
| `--color-brand-teal-accessible` | `#1A8070` | Interactive text, links, active states |
| `--color-brand-teal` | `#2BA692` | Decorative only |
| `--color-brand-teal-light` | `#E8F7F5` | Backgrounds, callout boxes |
| `--color-brand-charcoal` | `#383F47` | Body text |
| `--color-brand-mid-grey` | `#636A72` | Secondary text |
| `--color-brand-light-grey` | `#DCDCDC` | Borders and dividers |

The teal-accessible variant (`#1A8070`) is the WCAG-compliant interactive colour; the brighter teal (`#2BA692`) is decorative only and never used for text or interactive elements that need to clear contrast checks.

## Typography

Plus Jakarta Sans, loaded via Google Fonts at `https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;700&display=swap`.

- Body: 16px / Regular weight / 1.5 line height
- Headings: brand navy colour, weight scales with hierarchy
- Body text: brand charcoal colour

Plus Jakarta Sans is the platform UI typeface. Surface-specific typography (for example, the deck's serif headlines in Cormorant Garamond and DM Serif Display) is named in the surface file itself; this document covers brand typography, not editorial typography.

## Environment tag colours

For agent lifecycle and promotion state surfaces when those land at Phase 2. Each environment has a dot, fill, border, and text colour:

| Environment | Dot | Fill | Border | Text |
|-------------|-----|------|--------|------|
| Dev | `#534AB7` | `#EEEDFE` | `#AFA9EC` | `#26215C` |
| SIT | `#185FA5` | `#E6F1FB` | `#85B7EB` | `#042C53` |
| UAT | `#854F0B` | `#FAEEDA` | `#EF9F27` | `#412402` |
| Prod | `#A32D2D` | `#FCEBEB` | `#F09595` | `#501313` |
| Sandbox | `#5F5E5A` | `#F1EFE8` | `#B4B2A9` | `#2C2C2A` |

Padhanam's deployment model is one production posture per deployment per the local-first principle, so environment promotion as data-within-a-tenant is not a Padhanam commitment. These colours are available for agent-lifecycle states (draft, published, deprecated, archived) and for the optional environment surface an Apache 2.0 deployer running a SaaS layer on top of Padhanam would build.

## Logo

No logo committed at this version of the brand. The brand currently lives at the colour-and-typography level. Logo development sits with deck v1 drafting or a dedicated brand session.

## Implementation

Design tokens live at `charter/brand/tokens.css` as a CSS variables file matching the colour and typography choices above. The tokens file is consumed by the deck (`charter/deck.html`) and by any future Padhanam UI surface. Light-mode and dark-mode variants are committed in the tokens file.

## Cadence

Refreshed at phase audits per D45's cadence pattern. Material brand changes (colour shifts, typography changes, logo additions) land as strategic-block commits with rationale captured in the session log entry.
