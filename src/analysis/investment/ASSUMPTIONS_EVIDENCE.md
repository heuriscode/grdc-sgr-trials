# Evidence behind the investment-analysis assumptions (researched 24 Nov 2026)

`[snippet]` = figure from a search extract (source page blocked automated fetches: agriculture.gov.au, grdc.com.au) — check before publication.
`[judgement]` = analyst assumption. Everything else was read from the source.

## Region and zones
- GRDC Southern region = SA, Vic, Tas (all NSW now with the Northern panel) [snippet: GRDC growing regions page].
- Zone grain area, avg 2018-19 to 2020-21: SA Midnorth-Lower Yorke Eyre 1.70 Mha; SA Vic Mallee 2.79 Mha; SA Vic Bordertown-Wimmera 1.81 Mha; Vic High Rainfall 0.35 Mha; Tas Grain 8.8 kha — Ouzman, Azeem & Llewellyn 2025, *Impact of weeds on Australian grain and cotton production*, GRDC CSP2307-001RTX, Table 1. Cross-checked by apportioning ABS *Agricultural Commodities 2020-21* SA2 data to zones (1.72 / 2.93 / 1.75 / 0.375 Mha).
- 2024-25 winter crop area SA 3.82 Mha, Vic 4.03 Mha (ABS *Australian Agriculture: Broadacre Crops 2024-25*).
- Farm crop area: ABS 2020-21 grain ha per wheat-growing business (869 / 1,538 / 780 / 432 ha) and GRDC Farm Practices Survey 2021 Table 3 representative farm crop area (1,482 / 1,923 / 1,028 / 633 ha).
- Equity: A$1,683–2,765 per ha operated, 85–89% equity ratio (ABARES 2006-07 to 2008-09 benchmarks; Hooper & Levantis 2011 via Greijdanus & Kragt 2014, UWA WP1400002). Scaled for CPI and land values [judgement].
- Site zones: Appila, Edillilie, Hart, Roseworthy → SA Midnorth-LYE; Kinnabulla, Manangatang → SA Vic Mallee; Wallup → Bordertown-Wimmera; Streatham, Warrambine → Vic HRZ.

## Adoption (realised, not ex-ante)
- RDC evaluations show "adoption optimism": "optimistic in the light of previous experience" — Productivity Commission 2011, *Rural Research and Development Corporations*, pp.109, 123. Returns re-estimated at a median of 9.8% vs 39% reported — Hurley, Rao & Pardey 2014, AJAE 96(5) [snippet]. Pannell 2024: assumptions "too optimistic, sometimes much too optimistic".
- Extension moved the start of adoption earlier, but not its rate or ceiling (WA lupins) — Marsh, Pannell & Lindner 2000 [snippet] → the project is credited with **years of advance**.
- GRDC Farm Practices Survey 2021 (n=1,200):
  - Pulse share of crop area 22–24% in SA/Vic zones (price-driven).
  - N decision-support tools used by 22% of southern growers.
  - VRT on 11% of national crop area after 15+ years.
- Intercropping area fell 20% in 2016-17 and 50% between 2011-12 and 2013-14. Cover cropping was 189 kha (<1% of crop area) — ABS 4627.0 [snippet].
- ADOPT studies: average time to peak 9–19 years — Raffeld et al. 2025, *Agric. & Environ. Letters* [snippet]. No published ADOPT run for intercropping or cover crops.
- Ceilings, lags and dis-adoption by class: see `investment_assumptions.yaml` (`adoption.*`).

## Prices and costs
- Prices:
  - FAOSTAT producer prices for Australia (ABS gross unit values) 1995–2025, plus ABS levy local values 2022-23 to 2024-25.
  - CPI: ABS 6401.0 financial-year mean.
  - Urea and Brent: World Bank Pink Sheet, converted with FRED AUD/USD (relative movements only).
- 2026 input shock: urea ~A$675/t (Feb) → A$1,000–1,350/t (Mar–Apr 2026); domestic urea +80%; diesel +88% (UWA Apr 2026; Reuters Apr 2026; ABARES Jun 2026) [snippet].
- Hay: old-season oaten in the low $200s/t, new-season ~$300/t — Dairy Australia/AFIA Hay Report, 31 Oct 2025 [snippet]. Hay-making cost and agistment value are [judgement].
- Multicropping:
  - Contract grain separation costs $24/t (Mitchell et al. 2022) and $30/t (Roberts & Day 2022); the pipeline uses $25/t.
  - Contract cleaning cut GM by $30–60/ha at Waikerie (Roberts et al. 2019).
  - Capital items (seeder modification, storage, harvest set-up) are [judgement] — dealer quotes needed.
- Finance:
  - Small-business lending: RBA F5 small-business variable rate 9.25% (Oct 2026); F7 new small-business loans 7.14% (Sep 2026).
  - Public discount rate: 5% real, horizon investment + 30 years (CRRDC guidelines as applied in Agtrans assessments) [snippet].

## Project
- GRDC $7.6M + University of Adelaide $6.1M; nine sites SA/Vic; Dec 2022–Jun 2027 [snippet: GRDC Groundcover 2024; growag.com].
- Probability of success 0.6 and attribution 0.35 are [judgement]. NSW DPI ERR 19 credited 35% of conservation-farming adoption to DPI.

## Risk methods
- SERF: Hardaker et al. 2004, AJARE 48:253. CRRA on wealth: Hardaker 2010, AJARE. rr 0–4 (Anderson & Dillon 1992).
- Barrett & Donald 2003, Econometrica 71:71–104 (stochastic dominance test).
