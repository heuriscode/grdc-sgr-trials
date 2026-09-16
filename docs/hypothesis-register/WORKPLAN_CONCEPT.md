# Systems Hypothesis Register — workplan concept

**Project:** GRDC Farming Systems South (FSS), Phase 1
**For:** MK (project lead) — approval and resourcing
**Status:** Concept for discussion. Effort figures are indicative and need KS/MB/GM confirmation.

---

## 1. The problem

The FSS trials have run since 2023 across 9 sites and 912 plots. The data pipeline
validates and processes that data and computes yields, input rates, costs and gross
margins. What the project cannot currently do is say whether any result **supports or
contradicts what we expected** — because the expectations were never written down.

The consequence is concrete, not theoretical:

- **There is no hypothesis register.** The systems mapping's
  `System detailed description` field is populated in 1 row out of 912, and that row
  is the header example.
- **The system grouping itself is unsettled.** Two different aggregations of the same
  systems exist in the project's own files with conflicting labels
  (`More pulses`/`Increase pulses`, `Pulse on pulse`/`Pulse`). Neither has been ruled on.
- **The comparator is undefined.** "Baseline" is 21 different treatments across the 9
  sites — four at Streatham alone. Nothing records which one a given system should be
  tested against.
- **The comparison code does not run.** `system_baseline_comparisons.py`, the only
  module in the pipeline that attempts a system-vs-baseline test, fails on execution
  (undefined variables, a column renamed out from under it, and two library calls
  removed in the NumPy/pandas versions the project pins). Were it to run, its
  significance flag is inverted and its standard errors are understated by
  pseudo-replication.

So the position is not that analysis needs improving. **The project has no working
system-vs-baseline inference, and nothing to point it at.** These are one problem and
this mini-project fixes both.

There is also a scientific integrity dimension. Writing expectations down *after*
seeing results is not a hypothesis test. The register must be fixed and signed off
before the tests run — which is also what makes a multiplicity correction across ~100+
contrasts defensible rather than post-hoc.

---

## 2. What this delivers

1. **A ruled systems mapping.** An agreed grouping of all 912 plots, with any second
   dimension (N strategy, time of sowing, termination timing) factored out explicitly.
   Authored by the agronomy team, keyed into the pipeline.
2. **A comparator ruling.** For every system, which baseline it is tested against, and
   the rule where that varies by site.
3. **Mechanism narratives.** For every system: what changes, through what mechanism,
   over what timeframe, what would falsify it, and how confident the experts are. A
   publishable project asset in its own right, independent of the statistics.
4. **The hypothesis register.** Machine-readable, signed off by the agronomy team, one
   row per testable claim, driving automated testing.
5. **A prioritised measurement gap list.** Hypotheses that cannot be tested on current
   data are recorded rather than discarded, ranked by how much expert weight sits behind
   them — direct evidence for Phase 2 data integration priorities.

---

## 3. Why now, and why this shape

**It closes out Phase 1 deliverables.** Reporting against trial expectations is a
project obligation. Right now that reporting has no defensible basis.

**It is the mechanism for bringing MB and GM properly into project work.** Both have
been under-used relative to their expertise and are, reasonably, frustrated by it.
This mini-project is built so that the **agronomists hold the decision rights**: the
grouping is theirs to re-cut, the comparators are theirs to rule on, and nothing enters
the register without their sign-off. It asks for their judgement first and their
paperwork second.

**The burden is deliberately placed away from them.** The design is two-stage: MB and
GM write free-text mechanism narratives — the thing they are expert at and can do
quickly — and the decomposition into structured, testable records is done for them and
returned as a review sheet. They are never asked to fill in a statistics grid.

**The scope is far smaller than it looks.** 912 plots and 109 site-level treatments
collapse to **18 system groups**. That reframing is what makes this resourceable, and
is probably why previous attempts stalled — the task has been presented as unbounded.

---

## 4. Scope

**In scope:** the 18 system groups (subject to MB/GM re-cutting them), the comparator
rulings, mechanism narratives, the decomposed register, and agronomist sign-off.

**Out of scope for this mini-project:** building the deferred measures (fuel, labour,
machinery hours, emissions, soil moisture and N, PredictaB, weather, biomass). These
are recorded against hypotheses and prioritised, but built in a second pass.

**Not costed here:** pipeline, data and analysis work — including the register tooling,
the automated test engine and the re-keying of the systems mapping — is provided within
existing arrangements and carries no cost against this plan.

---

## 5. Roles

| Who | Role |
|---|---|
| **KS** | Lead. Owns collation, coordination and schedule. Convenes the workshops, prepares the reconciliation pack, manages the sign-off round, and is the single point of contact for MB and GM. |
| **MB** | Agronomist author (primary). Mapping critique and mechanism narratives; lead author on the larger share of systems. |
| **GM** | Agronomist author and **senior arbiter**. Mapping critique and narratives; rules on splits, merges and comparators where MB and GM differ. |
| **MK** | Oversight, resourcing, and sign-off on the ruled mapping (§6, W3) — because re-keying the mapping changes how project results are reported. |

Deliberate design points: **GM arbitrates rather than reviews**, which gives the
professorial role real authority rather than a courtesy pass. **Disagreement between MB
and GM is recorded in the register, not flattened** — two experts differing on a
mechanism is itself a finding.

---

## 6. Workstreams and schedule

Indicative 10-week schedule. Can compress to ~7 weeks by running W2 and W4 concurrently
if Phase 1 close-out demands it.

| | Workstream | Weeks | Who | Output |
|---|---|---|---|---|
| **W1** | **Kickoff workshop** (2h). Frame the task, walk the 18 groups and the flagged mis-aggregations, agree the working method. | 1 | KS, MB, GM | Agreed method, allocation of systems between MB and GM |
| **W2** | **Mapping critique.** Each of the 18 groups checked for coherence: split, merge, re-cut, or declare a second dimension. Agronomy team's call. | 2–3 | MB, GM | Marked-up mapping proposals |
| **W3** | **Reconciliation workshop** (3h) + arbitration. Resolve MB/GM differences; GM rules. Comparators ruled at the same sitting. **MK sign-off on the ruled mapping.** | 4 | KS, MB, GM (MK for sign-off) | **Ruled systems mapping + comparator rulings** |
| **W4** | **Mechanism narratives.** Stage 1 template, one section per ruled system. Split between MB and GM by allocation from W1. | 5–7 | MB, GM | Completed Stage 1 narratives |
| **W5** | **Collation and decomposition.** Narratives collated, gaps chased, decomposed into the structured register. | 7–8 | KS | Draft register |
| **W6** | **Sign-off round.** Draft register returned to MB and GM as a review sheet: is this a faithful reading of what you said? | 9 | MB, GM | Signed-off register |
| **W7** | **Close-out.** Final QA, measurement gap list ranked, handover. | 10 | KS | **Hypothesis register v1.0** + prioritised gap list |

**Gate:** W3 is a hard gate. Narratives cannot be written against a grouping that is
still moving, so W4 does not start until the mapping is ruled and signed off.

---

## 7. Effort

| | W1 | W2 | W3 | W4 | W5 | W6 | W7 | **Total** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **KS** | 1.0 | 1.0 | 1.0 | 1.0 | 2.0 | 1.5 | 1.0 | **8.5 d** |
| **MB** | 0.25 | 1.5 | 0.25 | 3.0 | — | 1.0 | — | **6.0 d** |
| **GM** | 0.25 | 1.0 | 1.0 | 2.0 | — | 0.75 | — | **5.0 d** |
| | | | | | | | | **19.5 d** |

Roughly **2 days per week each for MB and GM across a 10-week window**, with KS
carrying the coordination load. KS's W2 and W4 allocations are chase-and-support, not
authoring.

Indicative only — these need confirming with KS, MB and GM before they are committed to.

---

## 8. Decisions needed from MK

1. **Approve the effort allocation** — 8.5 KS / 6.0 MB / 5.0 GM days over 10 weeks.
2. **Confirm MB and GM have decision rights over the systems grouping.** This is the
   load-bearing decision. If the grouping is not genuinely theirs to change, the
   engagement premise fails and we will likely get the same non-return as previous
   attempts.
3. **Accept that the ruled mapping may change how results are reported.** If MB and GM
   split `Responsive` into four systems — and on the evidence they probably should —
   reporting categories move with it. Better now than after Phase 1 reporting.
4. **Confirm the Phase 1 close-out date** the register must land inside, so we know
   whether to run the 10-week or the compressed 7-week schedule.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Previous requests for this produced no return | Root cause addressed directly: the task is bounded at 18 systems not 109, the burden is narrative rather than tabular, and decision rights sit with the agronomists rather than with the request. |
| MB/GM availability over a 10-week window | ~2 days/week each. KS holds the schedule and escalates early rather than at the deadline. |
| The mapping critique reopens more than expected | This is a success, not a failure — it is exactly what the exercise is for. W3 gate and GM's arbitration keep it from running open-ended. |
| Narratives predict things the trial cannot measure | Expected and designed for. Captured as `test_pass = 2` and ranked; nothing is discarded for being currently unmeasurable. |
| Register is written to fit results already seen | The W3/W6 sign-off sequence fixes the register before tests run, and attribution and confidence are recorded per hypothesis. |

---

## 10. What this unblocks

Once the register exists and is signed off, testing every hypothesis in it becomes an
automated step rather than a piece of analytical work — results regenerate whenever data
updates, with directional verdicts against declared expectations. That converts the
bulk of trial reporting from manual effort into pipeline output, and frees the project's
analytical capacity for exploratory research rather than routine deliverables.

It also supplies Phase 2 with a ranked, expert-weighted list of what to measure next,
grounded in hypotheses the agronomy team has actually committed to rather than in a
generic wish list.

---

## Appendix — evidence for the mapping critique

Groups most likely to be wrong, on the current aggregation:

| Group | Sites | Plots | Distinct labels merged | Concern |
|---|---:|---:|---:|---|
| **Responsive** | 8 | 117 | 11 | Merges `Adviser (risk-averse / neutral / tolerant)`, `N bank`, `Less chemical inputs`, `Enhance soil health`, `Organic fertiliser`, `Persistent pasture`. These share only the property of being decision-rule driven. Almost certainly several distinct systems. |
| **Baseline** | 9 | 165 | 14 | Spans N rate and time-of-sowing variants. **This is the comparator for everything else**, so getting it wrong contaminates every contrast. |
| **Winter cover crop** | 7 | 102 | 6 | Merges `Early TOT`, `Late TOT`, `Mixed`, `Alternative`. Termination timing is plausibly a first-order treatment. |
| **Intercropping** | 3 | 54 | 4 | `Full / Half / Nil N intercrop` — a factorial N design flattened into a system label. |
| **Canola** | 1 | 36 | 3 | `High / Low / Mid N` — same issue. |
| **Companion cropping** | 3 | 39 | 4 | Merges N variants with `frequent`, which is a different treatment axis. |

The project has already prototyped the fix: the Hart-only mapping file factors
`Nitrogen strategy` (High/Low/Mid/Nil) out as its own column alongside a
`Gross system category`. Generalising that two-dimensional treatment to all 9 sites is
likely the single highest-value outcome of W2.
