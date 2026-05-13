# Flowstate source pack (S30b demo)

Operator-uploaded source pack for the Flowstate-McKinsey ProblemFramer
demonstration on tenant alpha. Six DOCUMENT-boundary markdown files
split from the operator's PDF pack at pre-session setup per
`briefs/p8/s30b.md`.

## Files

| File | Pack origin |
| --- | --- |
| [01_ceo_memo.md](01_ceo_memo.md) | CEO memo framing the Q3 growth-miss problem |
| [02_q3_review_deck.md](02_q3_review_deck.md) | Q3 board-level review deck content |
| [03_metrics_appendix.md](03_metrics_appendix.md) | Cohort metrics appendix |
| [04_team_lead_interviews.md](04_team_lead_interviews.md) | Synthesised team-lead interviews |
| [05_customer_research_notes.md](05_customer_research_notes.md) | Customer research notes |
| [06_competitive_intel.md](06_competitive_intel.md) | Competitive intelligence summary |

The brief's pre-session step 3 expects these six files to exist at
DOCUMENT boundaries (CEO memo, deck, appendix, interviews, research,
intel). The PDF split lands actual prose at each path before the demo
script runs.

## Demo invocation

After the operator drops content into the six files, run:

```sh
examples/p8_demo.sh
```

The script ingests these six files into tenant alpha via
`padhanam ingest run`, creates a Flowstate-McKinsey ProblemFramer
agent via `padhanam agent create` (methodology = McKinsey 7-Step,
role = ProblemFramer, source_ids = the six ingested ids), then runs
the demo via `padhanam agent run` with the input at
[_input.txt](_input.txt). The agent's streamed output captures to
`demos/p8_flowstate_output.md`.

## Facilitator notes (operator reference)

The pack's worked interpretation is preserved at
`_evaluation_benchmark/facilitator_notes.md`. The notes are not
ingested; they exist for the S30b reflection's qualitative comparison
of agent output against the pack's intended SMART problem statement.
