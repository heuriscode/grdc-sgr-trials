# Stage 2 — The hypothesis register (schema)

**This is the machine-readable end state.** MB and GM do not fill this in. It is
produced by decomposing the Stage 1 narratives, and returned to them as a review
sheet for sign-off. One row here = one test the pipeline runs automatically.

---

## 1. The hypothesis record

| Field | Type | Meaning |
|---|---|---|
| `hypothesis_id` | `H###` | Stable identifier. Never reused. |
| `system` | enum | The system group, **as ruled by MB/GM in Stage 1** — not necessarily one of the current 18. |
| `system_dimension` | enum / null | The second dimension where one was declared (e.g. `N_strategy=Low`, `TOS=TOS2`, `TOT=Early`). |
| `sites` | list | Sites the hypothesis applies to. `ALL` where general. |
| `comparator` | enum | The system the contrast is against, per the Stage 1 comparator ruling. |
| `comparator_rule` | text | How the comparator resolves where a site has several baselines. |
| `measure` | enum | A single variable from the measure spine (§2). One measure per row. |
| `direction` | `higher` / `lower` / `no_change` / `more_variable` / `unknown` | The directional claim. `no_change` is a real hypothesis and is tested as equivalence, not as a failure to reject. |
| `magnitude` | text / null | Expected effect size. Null where not claimed — absence is recorded, not guessed. |
| `timeframe` | enum | `within_season` / `by_year_2` / `full_rotation` / `beyond_trial` |
| `mechanism` | text | Why. Carried verbatim from Stage 1 — this is what makes a result interpretable. |
| `falsifier` | text | The result that would count as contradicting it. |
| `confidence` | `high` / `medium` / `low` / `no_prior` | Prior strength, from Stage 1. |
| `authored_by` | `MB` / `GM` / `both` | Attribution. |
| `dissent` | text / null | Where MB and GM disagreed, both positions, plus GM's arbitration. |
| `test_pass` | `1` / `2` | Pass 1 = testable on data held today. Pass 2 = requires a deferred measure (§3). |
| `test_spec` | ref | The statistical test, generated — not authored (§4). |
| `status` | enum | `draft` / `agronomist_signed_off` / `active` / `retired` |

### Rules

- **One measure per row.** A Stage 1 narrative predicting five things becomes five rows.
- **`no_prior` is recorded, never dropped.** It is what stops a null result being
  read as a disproved expectation that nobody actually held.
- **Dissent survives to the register.** Two experts disagreeing about a mechanism is a
  finding. Flattening it to consensus destroys information.
- **Nothing enters `active` without `agronomist_signed_off`.** The decomposition is our
  reading of their words; they get the final say on whether it is faithful.

---

## 2. Measure spine — pass 1 (testable on data held today)

Every one of these is either a validated field or already computed by the pipeline.

### Yield and output
| Measure | Source |
|---|---|
| `crop1_yield_kg_ha`, `crop2_yield_kg_ha`, `crop3_yield_kg_ha` | `schema_termination.py` |
| `plot_total_yield_kg_ha` | derived — sum of the three |
| `harvest_outcome` | `schema_termination.py` — enables crop-failure rate as a measure |
| `harvest_reason` | `schema_termination.py` |

### Economics
| Measure | Source |
|---|---|
| `plot_gross_margin_dollars` | `grossmargin.py` |
| `plot_revenue_dollars` | `grossmargin.py` |
| `operational_costs_dollars` | `prices_and_costs.py` |
| `material_input_costs_dollars` | `prices_and_costs.py` |
| `rotation_gross_margin_dollars` | `getCropSequenceGrossMargin()` — the crop-sequence unit |
| `gross_margin_variance` | derived — for risk and variability hypotheses |

### Nutrient inputs
| Measure | Source |
|---|---|
| `fert_applied_kg_ha` | `schema_fertiliser.py` |
| `N_applied_kg_ha` | derived — `nitrogenPercent × appliedAmount` |
| `P_applied_kg_ha` | derived — `phosphorousPercent × appliedAmount` |
| `n_fert_applications` | count per plot-season |

### Chemical inputs
| Measure | Source |
|---|---|
| `herbicide_applied_kg_ha`, `n_herbicide_applications` | `schema_herbicide.py` |
| `pesticide_applied_kg_ha`, `n_pesticide_applications` | `schema_pesticide.py` |
| `fungicide_applied_kg_ha`, `n_fungicide_applications` | `schema_fungicide.py` |
| `pest_targets` | `schema_pesticide.py` — `targetPest` |

### Management decisions
| Measure | Source |
|---|---|
| `sowing_density_g_m2`, `sowing_depth_mm` | `schema_sowing.py` |
| `sowing_date`, `sowing_timeliness` | `schema_sowing.py` |
| `sowing_reason`, `termination_state` | `schema_sowing.py` / `schema_termination.py` |
| `variety`, `seed_treatment` | `schema_sowing.py` |

### Sequence structure
| Measure | Source |
|---|---|
| `crop_sequence` | `grossmargin.py` |
| `legume_frequency`, `break_crop_frequency`, `fallow_frequency` | derived from the plot state series |
| `n_machine_passes` | derived — count of dated operations per plot-season |

> `n_machine_passes` is in pass 1 because it needs no new coefficients — it is a count
> of activity records. It is the bridge to the pass 2 derivations.

---

## 3. Measure spine — pass 2 (deferred, but recorded now)

**Deliberately deferred.** These are recorded against hypotheses with `test_pass = 2`
so that the register itself becomes the prioritisation evidence for building them.
Nothing is discarded for being unmeasurable today.

| Measure | What it needs |
|---|---|
| `fuel_L_ha`, `machinery_hrs_ha`, `labour_hrs_ha` | An operation → machinery coefficient table. The operation taxonomy already exists in `ActivitiesCosts.csv` (`SOWING`, `GROUND_SPRAYING_HA`, `FERT_SPREADING_HA`, `WINDROWING_HA`, `HARVEST_HA`). |
| `CO2e_kg_ha` | Diesel emission factor applied to `fuel_L_ha`. |
| `N2O_kg_ha` | Emission factor on `N_applied_kg_ha` — inputs already held. |
| `soil_moisture`, `soil_N` | Annual soil sampling integration. |
| `predicta_b` | PredictaB disease inoculum integration. |
| `rainfall`, `VPD`, `frost_days`, `heat_days` | BOM/weather integration with spatial join. |
| `biomass_kg_ha` | Biomass cut integration. |
| `events` | Event record integration. |
| `water_use_efficiency` | Yield + rainfall/soil moisture. Named in the FSS briefing note as a Phase 2 core objective. |
| `grazing_value` | Pasture systems. Also a named Phase 2 objective. |
| `carbon_sequestration` | Soil carbon. Also named in the briefing note. |

> Pass 2 ordering is **set by the register**, not independently: whichever deferred
> measure carries the most high-confidence hypotheses gets built first.

---

## 4. Test specification — generated, not authored

`test_spec` is derived from the record. Neither the agronomists nor the analysts
hand-pick a test per hypothesis; the register determines it.

| Record shape | Test |
|---|---|
| `direction` ∈ {`higher`,`lower`}, continuous measure | One-sided contrast, system vs comparator |
| `direction = no_change` | Equivalence test against a declared margin — *not* a failure to reject |
| `direction = more_variable` | Variance ratio test |
| Count measure (`n_*_applications`, `n_machine_passes`) | Count model, not a t-test on a mean |
| Categorical (`harvest_outcome`) | Proportion contrast |

### Three design constraints the test layer must respect

1. **Plot is not the unit of replication.** Plots nest in phase within system within
   site, and phases share year effects. Contrasts must be made **within phase**, with
   site and year as blocking factors. The existing code's own TODO flags this and it
   was never done.

2. **No all-pairs differencing.** The current `system_baseline_comparisons.py` forms
   every (system plot × baseline plot) difference and then treats the result as *n*
   independent observations. That is pseudo-replication; it understates the standard
   error by roughly √(n_system × n_baseline) and will manufacture significance.

3. **Multiplicity is declared up front.** The register fixes the number of tests
   *before* anyone looks at results, which is precisely what makes a family-wise
   correction defensible rather than post-hoc. This is the single biggest scientific
   argument for building the register at all.

---

## 5. Worked example

Stage 1 narrative (MB, on *More pulses*):

> "Two legume phases instead of one means the following cereal draws on fixed N, so
> applied N should come down materially from the second year. Yield in the cereal
> phase should hold or lift slightly through the disease break. Gross margin is the
> open question — pulse prices carry the result and the input saving may not cover a
> weaker pulse year."

Decomposes to four records:

| id | system | measure | direction | timeframe | conf | pass |
|---|---|---|---|---|---|---|
| H014 | More pulses | `N_applied_kg_ha` | lower | by_year_2 | high | 1 |
| H015 | More pulses | `crop1_yield_kg_ha` (cereal phase) | higher | full_rotation | medium | 1 |
| H016 | More pulses | `rotation_gross_margin_dollars` | unknown | full_rotation | no_prior | 1 |
| H017 | More pulses | `gross_margin_variance` | more_variable | full_rotation | medium | 1 |

H016 is the important one. "We genuinely did not know" is recorded as a prior, so
whichever way it lands, it is a finding rather than a retrofitted expectation.
