# Systems Hypothesis Register

A mini-project within GRDC Farming Systems South (FSS) Phase 1, to produce the
hypothesis register the trials have been running without.

## Contents

| File | Audience | Purpose |
|---|---|---|
| [`WORKPLAN_CONCEPT.md`](WORKPLAN_CONCEPT.md) | MK | Approval and resourcing. Covers KS/MB/GM effort only. |
| [`templates/STAGE1_mechanism_narratives.md`](templates/STAGE1_mechanism_narratives.md) | MB, GM | The working template. Pre-filled with all 18 systems, their sites, plot counts and the site-level treatments swept into each. Free text. |
| [`templates/STAGE2_register_schema.md`](templates/STAGE2_register_schema.md) | KS, data team | The machine-readable end state, the measure spine, and the test-generation rules. Agronomists review this, they do not fill it in. |

## The two-stage design

**Stage 1** asks MB and GM for two things: whether the system grouping is right (their
call — they can split, merge or re-cut it), and what they expect each system to do and
why. Free text, no grid.

**Stage 2** decomposes those narratives into one row per testable claim and returns it
to them as a review sheet for sign-off. The statistical test for each row is generated
from the record, not authored.

## Current state

- Stage 1 template: generated from `Systems plot ID mapping.csv`, pre-filled, ready for review.
- Stage 2 schema: drafted.
- Workplan: concept draft, effort figures indicative pending KS/MB/GM confirmation.

Regenerate the Stage 1 template after a mapping change rather than editing it by hand.

## Why the grouping is the first task, not an assumption

The 18-group aggregation was inferred, not agreed. Two conflicting aggregations already
exist in `data/reference_data/` with different labels for the same systems, and several
groups are carrying a factorial design (N rate, time of sowing, termination timing)
inside one flat label. The Hart-only mapping file already prototypes the fix by pulling
`Nitrogen strategy` out as its own dimension. Generalising that is likely the highest-value
outcome of the exercise.

`System detailed description` in the source mapping is populated in 1 row out of 912,
and that row is the header example.
