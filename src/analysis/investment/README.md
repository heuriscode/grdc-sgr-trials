# sgr_investment — benefit-cost (investment) analysis of the trial systems

Evaluates each system tested in the trials as an **investment decision for a cropping
farmer**, by GRDC agro-ecological zone. It then aggregates to an industry and
project-level benefit-cost analysis.

It plugs into the pipeline after the crop-sequence gross margin step (`src/head.py`):

```python
from src.analysis.investment import run_investment_analysis
run_investment_analysis()                       # central case, writes data/outputs/investment/<date>/
run_investment_analysis(input_shock=True)       # 2026 urea/diesel shock
run_investment_analysis(scenario="low")         # every parameter at its low bound
run_investment_analysis(baseline_rule={"HART": "Baseline (SDP N)"}, variant_rule="mean")
```

Run from the repo root. Requires numpy, pandas, scipy, pyyaml and matplotlib.

## What it does

| Step | Module | What |
|---|---|---|
| 1 | `inputs.py` | Reads the newest gross-margin output (it prefers the `_priced` folder, which carries urea quantities). Maps plots to broad categories (`system_broad_categories.csv`) and zones (`site_zones.csv`). Builds the whole-system GM per ha per year: the mean over the rotation's phases of the replicate-mean crop-sequence GM. A phase with no crop that year (e.g. fallow) counts as zero, because its costs are booked to the next crop. |
| 2 | `prices.py` | Sets central prices as the **median real** price over the last 10 years (FAOSTAT/ABS unit values, deflated by ABS CPI). Price simulation resamples whole historical years, which keeps the correlation between commodities and between grain and inputs. A `lognormal` alternative is available. Input-cost multipliers for operations, urea and other materials. |
| 3 | `simulate.py` | Monte Carlo of annual whole-system GM. Each draw is a site-year (the season), one replicate per phase, and a set of prices and costs. System and baseline share the season and prices (common random numbers). |
| 4 | `farm.py` | Representative farm per zone that converts part of its crop area over a ramp. Deducts extra labour, learning losses and, **for multicropping only**, capital (seeder modification, segregated storage, harvest set-up) with replacement and residual value. Reports NPV, P(NPV>0), NPV per converted ha per year, and BCR/IRR/payback where there is capital. |
| 5 | `industry.py` | Zone area × logistic adoption (ceiling, years to peak, lag, dis-adoption) × net gain per ha. See "Realism controls" below for the gain estimate and the adoption gate. Project benefit = the with-project curve minus the curve delayed by the years of advance × P(success) × attribution, against the $13.7M research cost. Systems compete for paddocks under a joint cap. |
| 6 | `risk.py` | First- and second-order stochastic dominance on simulated distributions, a Barrett-Donald bootstrap test on the observed data, SERF certainty equivalents (CRRA on wealth, rr 0–4), P(loss) and CVaR10. |
| 7 | `run.py`, `report.py` | Writes CSV outputs, CDF and SERF charts, and a tornado chart of project NPV sensitivity. |

### Realism controls (ruled: "realistic assumptions everywhere")

- **Adoption ceilings come from realised adoption, not ex-ante assessments.** Sources: GRDC Farm Practices Survey 2021, ABS land management statistics and ADOPT study ranges. No-till and similar exceptional innovations are not used as analogues.
- **The project is credited only with bringing adoption forward** (Marsh, Pannell & Lindner 2000). It is not credited with the whole adoption curve. It is also discounted for attribution and probability of success.
- **Shrinkage.** A system with one site and three seasons has a wide interval. Its mean gain is pulled towards zero by empirical-Bayes shrinkage (`gain_shrinkage.csv`).
- **Adoption gate.** Adoption is credited only where the representative farm's expected NPV at the shrunk gain is positive.
- **Confidence-weighted adoption (default).** Confidence is the share of 2,000 bootstrap resamples of the trial data (trial years and replicate plots drawn with replacement) in which a system's average gross margin beats its baseline's. Each system's adoption ceiling is multiplied by its confidence, so a system at 77% is credited with 77% of the uptake a proven system would get. Confidence is not the chance of a profit in any one year. Turn it off with `evidence_weighting=False`.
- **Evidence stress test.** `adoption.evidence_threshold` is off at 0.5. Setting it to 0.8 credits only systems with at least an 80% bootstrap probability of beating the baseline.

### Comparison with RDC impact-assessment conventions

`investment_assumptions_rdc_convention.yaml` is a cited overlay holding the assumptions common in published RDC impact assessments:
- maximum adoption of 20–25%, reached three years after a one-year lag and held for 30 years;
- no separate counterfactual;
- attribution of 50%;
- probability of success of 1.0.

It is for comparison only. Two functions run it:
- `run_convention_comparison()` runs the full analysis on this basis, with no shrinkage, no confidence weighting and each zone's best trial site.
- `convention_variant_table()` writes the realistic case plus variants A–D to `convention_comparison.csv`.

## Choices you can make

| Option | Default | Meaning |
|---|---|---|
| `baseline_rule` | `"auto"` | Picks which baseline variant(s) each site's systems are compared to. **`auto`** takes the variant with the most plots; a tie goes to a Mid/Medium N variant, otherwise to the mean of the tied variants. **`mean`** averages all variants. **`most_numerous`** takes the variant with the most plots and averages any tie, with no Mid N preference. **A category name** uses that variant. **A dict `{site: rule}`** sets a rule per site. |
| `variant_rule` | `"auto"` | The same choices, applied to the variants within each broad category (e.g. Canola Low, Mid or High N). |
| `scenario` | `central` | `low`, `central` or `high` for every parameter block. |
| `input_shock` | `False` | 2026 urea (×1.6) and operations (×1.15) shock. |
| `price_method` | `historical` | `historical` or `lognormal`. |
| `revenue_basis` | `recorded` | `recorded` anchors revenue to the pipeline's recorded revenue; yields only weight each crop's price. `yields` rebuilds revenue from the yields in the GM table. |
| `shrink_estimates` | `True` | Empirical-Bayes shrinkage of mean gains. |
| `evidence_weighting` | `True` | Confidence enters the adoption allocation (`gain × confidence` weights; with `reallocate_adoption=False`, the ceiling × confidence). |
| `reallocate_adoption` | `True` | Pool each zone's potential adoption area (all tested systems' ceilings, capped by `adoption.joint_cap_share`) and give it to the systems that pay. Weaker systems get none. |
| `cap_at_class_high` | `False` | When reallocating, cap each system at the high ceiling of its class. |
| `gain_selection` | `mean` | `best_site` credits each zone with its best site (comparison scenario only). |
| `profile` | `None` | Assumption overlay, e.g. `rdc_convention`. |
| `overrides` | `{}` | Fix any parameter, e.g. `{"discounting.public_rate": 0.07}`. |

## Assumptions

All assumptions are in `data/reference_data/investment_assumptions.yaml`. Each has a
low/central/high value, a unit, a **source** and a **status**:

- `verified`: read from the cited source.
- `snippet`: taken from a search extract.
- `judgement`: an analyst assumption.
- `data`: derived from trial data or a data file in this repo.

The loader refuses an uncited number. `assumptions_register.csv` in every output
folder lists them all.

Supporting reference data:

- `price_history.csv` (FAOSTAT/ABS 1995–2025; World Bank urea and Brent)
- `cpi_annual.csv` (ABS 6401.0)
- `site_zones.csv`
- `system_broad_categories.csv`. This was generated by rule, and its `confirmed` column should be set once the project team has checked it.

## Outputs (`data/outputs/investment/<dd_mm_YYYY>/`, git-ignored — real results)

| File | Content |
|---|---|
| `farm_investment_by_zone.csv` | Representative-farm NPV distribution, P(NPV>0), BCR/IRR/payback (multicrop) |
| `trial_evidence_gain_vs_baseline.csv` | Mean gain vs baseline with 90% bootstrap interval and confidence; replaces `system_baseline_comparisons` |
| `gain_shrinkage.csv` | Raw vs shrunk mean gains |
| `risk_summary_by_zone.csv` | Mean, SD, CV, P(loss), p10, CVaR10 for each system and its baseline |
| `stochastic_dominance.csv` | FSD/SSD verdicts (simulated) and Barrett-Donald p-values (observed) |
| `serf_certainty_equivalents.csv`, `serf_<zone>.png` | Certainty-equivalent gain over baseline across risk aversion |
| `industry_by_zone_system.csv` | Adoption, industry and project PV benefits, and each system's share |
| `project_summary.csv`, `project_annual_cashflow.csv` | Project NPV, BCR, IRR, P(NPV>0) |
| `sensitivity_project.csv`, `tornado_project_npv.png` | One-at-a-time sensitivity (common random numbers) |
| `data_query_revenue_vs_yield.csv` | Plot-years where recorded revenue ≠ yield × reference price — to check |
| `observed_system_gm_by_site_year.csv`, `cdf_<zone>.png`, `excluded_plots.csv`, `run_info.txt` | Supporting outputs |

## Limitations (stated in every run)

1. **Only three seasons (2023–2025).** Season risk is limited to those seasons. `seasons.year_weights` can tilt them towards long-run deciles but cannot add new seasons.
2. **Extrapolation from few sites.** Zone results rest on 1–4 sites. Some broad categories are tested at one site with three plots.
3. **Fertiliser price risk is understated.** Urea is only separable when the `_priced` gross margins exist. Otherwise fertiliser price risk sits in the general materials multiplier.
4. **Judgement-status assumptions must be confirmed before publication.** These include adoption ceilings, capital costs, agistment and hay-making costs.
5. **Benefits beyond the trial window are not valued.** Soil, weed-seedbank and carbon benefits that do not appear within the trial's gross margins are noted, not valued.
