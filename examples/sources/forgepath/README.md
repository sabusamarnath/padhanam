# Forgepath source pack (S30b demo)

Operator-uploaded source pack for the Forgepath-LVT LVTGuide
demonstration on tenant beta. Seven DOCUMENT-boundary markdown files
split from the operator's PDF pack at pre-session setup per
`briefs/p8/s30b.md`.

## Files

| File | Pack origin |
| --- | --- |
| [01_ceo_pre_read.md](01_ceo_pre_read.md) | CEO pre-read framing the strategic offsite |
| [02_market_landscape.md](02_market_landscape.md) | Market landscape analysis |
| [03_customer_segments.md](03_customer_segments.md) | Customer segment definitions |
| [04_financial_model.md](04_financial_model.md) | Financial model summary |
| [05_org_design_notes.md](05_org_design_notes.md) | Org-design notes |
| [06_prior_strategy_artefacts.md](06_prior_strategy_artefacts.md) | Prior strategy artefacts |
| [07_initiative_inventory.md](07_initiative_inventory.md) | Initiative inventory |

The brief's pre-session step 3 expects these seven files to exist at
DOCUMENT boundaries (pre-read, landscape, segments, model, org-design,
artefacts, inventory). The PDF split lands actual prose at each path
before the demo script runs.

## Demo invocation

After the operator drops content into the seven files, run:

```sh
examples/p8_demo.sh
```

The script ingests these seven files into tenant beta via
`padhanam ingest run`, creates a Forgepath-LVT LVTGuide agent via
`padhanam agent create` (methodology = LVT, role = LVTGuide,
source_ids = the seven ingested ids), then runs the demo via
`padhanam agent run` with the input at [_input.txt](_input.txt). The
agent's streamed output captures to `demos/p8_forgepath_output.md`.

## Facilitator notes (operator reference)

The pack's worked interpretation is preserved at
`_evaluation_benchmark/facilitator_notes.md`. The notes are not
ingested; they exist for the S30b reflection's qualitative comparison
of agent output against the pack's intended Lean Value Tree.
