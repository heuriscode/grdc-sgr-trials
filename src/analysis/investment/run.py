"""Entry point: run the full investment analysis and write outputs.

Called from ``src/head.py`` after the gross-margin step::

    from src.analysis.investment import run_investment_analysis
    run_investment_analysis()

Outputs go to ``data/outputs/investment/<dd_mm_YYYY>/`` (git-ignored: these are
real trial results).
"""

from __future__ import annotations

import datetime
import logging
import os
import zlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.utils.base_paths import get_outputs_path

from .config import Assumptions
from .farm import FarmResult, farm_analysis, farm_npv_at_mean_gain, farm_table
from .industry import industry_analysis, shrink_gains
from .inputs import (build_trial_data, load_gross_margins, load_site_zones, plot_year_gm,
                     reconcile_revenue, system_year_gm)
from .prices import build_price_model
from .risk import barrett_donald, dominance, risk_stats, serf
from .simulate import SystemSimulator

logger = logging.getLogger(__name__)


@dataclass
class RunOptions:
    gm_file: str | None = None            # None = newest gross-margin output
    revenue_basis: str = "recorded"       # or 'yields' (see inputs.build_trial_data)
    assumptions_file: str | None = None
    scenario: str = "central"             # low / central / high for all parameter blocks
    baseline_rule: object = "auto"        # 'auto' | 'mean' | 'most_numerous' | category | {site: rule}
    variant_rule: object = "auto"
    price_method: str = "historical"      # or 'lognormal'
    input_shock: bool = False             # 2026 urea/diesel shock scenario
    n_farm_iterations: int = 2000         # farm Monte Carlo iterations (each = farm_years seasons)
    n_risk_draws: int = 20000             # simulated seasons per zone x system for risk ranking
    n_bootstrap: int = 2000               # bootstrap of mean GM gain
    n_industry_draws: int = 5000
    seed: int = 20261124
    shrink_estimates: bool = True         # empirical-Bayes shrinkage of mean gains (industry/project)
    evidence_weighting: bool = True       # scale adoption by confidence that the system beats baseline
    run_serf: bool = True
    run_sensitivity: bool = True
    output_dir: str | None = None
    overrides: dict = field(default_factory=dict)  # {'discounting.public_rate': 0.07, ...}


def _out_dir(opts: RunOptions) -> str:
    if opts.output_dir:
        d = opts.output_dir
    else:
        d = os.path.join(get_outputs_path(), "investment", datetime.datetime.now().strftime("%d_%m_%Y"))
    os.makedirs(d, exist_ok=True)
    return d


def _core(td, a: Assumptions, opts: RunOptions, rng: np.random.Generator, zones: pd.DataFrame,
          with_risk: bool = True) -> dict:
    pm = build_price_model(a, opts.scenario)
    sim = SystemSimulator(td, a, opts.baseline_rule, opts.variant_rule)
    central = pm.central_draw()
    if opts.input_shock:  # long-run gains (industry/project) under the shocked input costs
        central["m_urea"] = central["m_urea"] * a.get("costs.shock_urea_multiplier", opts.scenario)
        central["m_op"] = central["m_op"] * a.get("costs.shock_operations_multiplier", opts.scenario)

    # observed whole-system GMs at central prices/costs (trial evidence)
    gm_rows = plot_year_gm(td, central["prices"][0], central["m_op"][0], central["m_mat"][0], central["m_urea"][0])
    observed = system_year_gm(td, gm_rows, opts.baseline_rule, opts.variant_rule)

    zone_sites = zones.groupby("zone")["site"].apply(list).to_dict()
    broads = sorted(b for b in td.structure["broad_category"].unique() if b != "Baseline")

    farm_results: list[FarmResult] = []
    zone_deltas, farm_npv = {}, {}
    risk_rows, sd_rows, serf_frames, sim_store = [], [], [], {}
    for zone, sites in zone_sites.items():
        sites = [s for s in sites if s in set(td.structure["site"])]
        if not sites:
            continue
        risk_draws = pm.draw(opts.n_risk_draws, rng, opts.price_method, opts.input_shock) if with_risk else None
        dists = {}
        for broad in broads:
            # one random stream per zone x system, so results do not depend on run order or
            # on which other analyses ran (common random numbers across sensitivity cases)
            k_rng = np.random.default_rng([opts.seed, zlib.crc32(f"{zone}|{broad}".encode())])
            fr = farm_analysis(sim, pm, a, zone, sites, broad, opts.n_farm_iterations, k_rng,
                               opts.scenario, opts.price_method, opts.input_shock)
            if fr is None:
                continue
            farm_results.append(fr)
            zone_deltas[(zone, broad)] = sim.bootstrap_mean_delta(sites, broad, central, opts.n_bootstrap, k_rng)
            fr.summary["observed_mean_gain_per_ha"] = _observed_mean_gain(observed, sites, broad)
            if not with_risk:
                continue
            s = sim.simulate_zone(sites, broad, risk_draws, rng)
            sim_store[(zone, broad)] = s
            dists[broad] = s["gm_system"].to_numpy()
            dists.setdefault("Baseline", s["gm_baseline"].to_numpy())
            # paired baseline for this system's sites (CRN)
            base = s["gm_baseline"].to_numpy()
            st = risk_stats(dists[broad])
            stb = risk_stats(base)
            d = dominance(dists[broad], base)
            obs = observed[(observed["broad_category"] == broad) & observed["site"].isin(sites)]
            obs_base = observed[(observed["broad_category"] == "Baseline")
                                & observed["site"].isin(obs["site"].unique())]
            p1 = barrett_donald(obs["gm"].to_numpy(), obs_base["gm"].to_numpy(), 1, 499, rng)
            p1r = barrett_donald(obs_base["gm"].to_numpy(), obs["gm"].to_numpy(), 1, 499, rng)
            p2 = barrett_donald(obs["gm"].to_numpy(), obs_base["gm"].to_numpy(), 2, 499, rng)
            p2r = barrett_donald(obs_base["gm"].to_numpy(), obs["gm"].to_numpy(), 2, 499, rng)
            risk_rows.append({"zone": zone, "broad_category": broad,
                              "sites": ", ".join(sorted(s["site"].unique())),
                              **{f"system_{k}": v for k, v in st.items()},
                              **{f"baseline_{k}": v for k, v in stb.items()},
                              "mean_gain": st["mean"] - stb["mean"],
                              "p_system_beats_baseline": float((s["delta"] > 0).mean())})
            sd_rows.append({"zone": zone, "broad_category": broad, "simulated_verdict": d["verdict"],
                            "simulated_fsd": d["fsd"], "simulated_ssd": d["ssd"],
                            "n_observed_system": len(obs), "n_observed_baseline": len(obs_base),
                            "bd_p_fsd_system_over_baseline": p1, "bd_p_fsd_baseline_over_system": p1r,
                            "bd_p_ssd_system_over_baseline": p2, "bd_p_ssd_baseline_over_system": p2r,
                            "observed_note": "3 seasons per site - low test power" })
            if opts.run_serf:
                wealth = a.get("risk.wealth_per_ha", opts.scenario)
                sf = serf({broad: dists[broad], "Baseline": base}, wealth)
                sf = sf[sf["system"] == broad].assign(zone=zone)
                serf_frames.append(sf)

    # realistic expected gains: shrink noisy estimates towards zero, then gate adoption on
    # the representative farm's expected NPV at the shrunk mean gain
    if opts.shrink_estimates:
        gains, shrinkage = shrink_gains(zone_deltas)
    else:
        gains, shrinkage = zone_deltas, pd.DataFrame()
    for k in list(gains):
        mean_gain = float(np.mean(gains[k])) if len(gains[k]) else np.nan
        farm_npv[k] = farm_npv_at_mean_gain(a, k[0], k[1], mean_gain, opts.scenario)
    for fr in farm_results:
        k = (fr.zone, fr.broad)
        fr.summary["shrunk_mean_gain_per_ha"] = float(np.mean(gains[k])) if len(gains.get(k, [])) else np.nan
        fr.summary["farm_npv_at_shrunk_mean_gain"] = farm_npv.get(k, np.nan)
    confidence = {k: float(np.mean(v > 0)) for k, v in zone_deltas.items() if len(v)}
    industry = industry_analysis(a, gains, farm_npv, opts.n_industry_draws,
                                 np.random.default_rng(opts.seed + 1), opts.scenario,
                                 confidence=confidence, evidence_weighting=opts.evidence_weighting)
    tab = industry["table"]
    if not tab.empty:
        f = farm_table(farm_results)[["zone", "broad_category", "sites"]]
        tab = tab.merge(f, on=["zone", "broad_category"], how="left")
        tab["n_sites"] = tab["sites"].fillna("").str.split(", ").map(lambda x: len([s for s in x if s]))
        total = tab["pv_project_benefit_mean"].clip(lower=0).sum()
        tab["share_of_project_benefit"] = tab["pv_project_benefit_mean"].clip(lower=0) / total if total > 0 else 0.0
        industry["table"] = tab
    evidence = []
    for (zone, broad), boot in zone_deltas.items():
        evidence.append({"zone": zone, "broad_category": broad, "mean_gain_per_ha": float(np.mean(boot)),
                         "ci90_low": float(np.percentile(boot, 5)), "ci90_high": float(np.percentile(boot, 95)),
                         "confidence_beats_baseline": float((boot > 0).mean())})
    observed_gain = {k: float(v) for k, v in
                     ((k, _observed_mean_gain(observed, zone_sites[k[0]], k[1])) for k in farm_npv)}
    return {
        "zone_deltas": gains, "farm_gate": farm_npv, "observed_gain": observed_gain,
        "confidence": confidence,
        "shrinkage": shrinkage,
        "price_model": pm, "observed": observed, "farm": farm_table(farm_results),
        "farm_results": farm_results, "industry": industry,
        "risk": pd.DataFrame(risk_rows), "dominance": pd.DataFrame(sd_rows),
        "serf": pd.concat(serf_frames, ignore_index=True) if serf_frames else pd.DataFrame(),
        "evidence": pd.DataFrame(evidence), "simulations": sim_store,
    }


def _observed_mean_gain(observed: pd.DataFrame, sites: list[str], broad: str) -> float:
    """Mean over sites of the mean annual GM gain vs baseline (central prices)."""
    o = observed[(observed["broad_category"] == broad) & observed["site"].isin(sites)]
    return float(o.groupby("site")["gm_vs_baseline"].mean().mean())


SENSITIVITY_PARAMS = [
    "discounting.public_rate", "project.probability_of_success", "project.attribution_share",
    "project.adoption_advance_years", "adoption.joint_cap_share", "prices.grain_price_level",
    "costs.operations_level_index", "adoption.rotation.ceiling_share", "adoption.multicrop.ceiling_share",
    "adoption.rotation.years_to_peak", "adoption.evidence_threshold", "adoption.multicrop.years_to_peak",
]


INDUSTRY_ONLY_PREFIXES = ("project.", "adoption.", "discounting.public_rate", "zones.")


def _fix_param(a: Assumptions, p: str, val) -> Assumptions:
    """Copy of the assumptions with a parameter fixed (low = central = high = val)."""
    a2 = a.with_overrides()
    node = a2.tree
    parts = p.split(".")
    for k in parts[:-1]:
        node = node[k]
    node[parts[-1]] = {**node[parts[-1]], "low": val, "central": val, "high": val}
    return a2


def sensitivity(td, a: Assumptions, opts: RunOptions, zones: pd.DataFrame, base: dict) -> pd.DataFrame:
    """One-at-a-time low/high on key parameters -> project NPV and BCR (tornado data).

    Every case reuses the main run's seed (common random numbers), so differences come
    from the parameter, not from Monte Carlo noise. Industry/adoption parameters reuse
    the main run's gross-margin results and adoption gate; price and cost parameters
    re-run the farm stage.
    """
    rows = []
    for p in SENSITIVITY_PARAMS:
        lo, c, hi = a.triple(p)
        for label, val in (("low", lo), ("high", hi)):
            a2 = _fix_param(a, p, val)
            if p.startswith(INDUSTRY_ONLY_PREFIXES):
                gate = base["farm_gate"]
                if p.startswith("adoption.") or p == "discounting.farm_rate":
                    gate = {k: farm_npv_at_mean_gain(a2, k[0], k[1], float(np.mean(base["zone_deltas"][k])), opts.scenario)
                            for k in base["farm_gate"] if len(base["zone_deltas"].get(k, []))}
                ind = industry_analysis(a2, base["zone_deltas"], gate, opts.n_industry_draws,
                                        np.random.default_rng(opts.seed + 1), opts.scenario,
                                        confidence=base["confidence"], evidence_weighting=opts.evidence_weighting)
            else:
                small = RunOptions(**{**opts.__dict__, "run_serf": False})
                ind = _core(td, a2, small, np.random.default_rng(opts.seed), zones, with_risk=False)["industry"]
            pr = ind["project"]
            rows.append({"parameter": p, "case": label, "value": val, "npv": pr["npv_mean"], "bcr": pr["bcr_mean"]})
    return pd.DataFrame(rows)


def run_investment_analysis(options: RunOptions | None = None, **kwargs) -> dict:
    """Run the analysis end-to-end and write csv outputs and charts. Returns the results."""
    opts = options or RunOptions(**kwargs)
    a = Assumptions.load(opts.assumptions_file)
    if opts.overrides:
        a = a.with_overrides(**opts.overrides)
    rng = np.random.default_rng(opts.seed)
    td = build_trial_data(load_gross_margins(opts.gm_file), revenue_basis=opts.revenue_basis)
    zones = load_site_zones()
    res = _core(td, a, opts, rng, zones)
    if opts.run_sensitivity:
        res["sensitivity"] = sensitivity(td, a, opts, zones, res)

    out = _out_dir(opts)
    pd.DataFrame(a.register()).to_csv(os.path.join(out, "assumptions_register.csv"), index=False)
    res["observed"].to_csv(os.path.join(out, "observed_system_gm_by_site_year.csv"), index=False)
    res["evidence"].to_csv(os.path.join(out, "trial_evidence_gain_vs_baseline.csv"), index=False)
    res["farm"].to_csv(os.path.join(out, "farm_investment_by_zone.csv"), index=False)
    res["risk"].to_csv(os.path.join(out, "risk_summary_by_zone.csv"), index=False)
    res["dominance"].to_csv(os.path.join(out, "stochastic_dominance.csv"), index=False)
    if not res["serf"].empty:
        res["serf"].to_csv(os.path.join(out, "serf_certainty_equivalents.csv"), index=False)
    res["industry"]["table"].to_csv(os.path.join(out, "industry_by_zone_system.csv"), index=False)
    if not res["shrinkage"].empty:
        res["shrinkage"].to_csv(os.path.join(out, "gain_shrinkage.csv"), index=False)
    pd.DataFrame([res["industry"]["project"]]).to_csv(os.path.join(out, "project_summary.csv"), index=False)
    res["industry"]["annual"].to_csv(os.path.join(out, "project_annual_cashflow.csv"), index=False)
    if "sensitivity" in res:
        res["sensitivity"].to_csv(os.path.join(out, "sensitivity_project.csv"), index=False)
    td.excluded.to_csv(os.path.join(out, "excluded_plots.csv"), index=False)
    reconcile_revenue(td).to_csv(os.path.join(out, "data_query_revenue_vs_yield.csv"), index=False)
    with open(os.path.join(out, "run_info.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"gross margin source: {td.source_path}\n")
        fh.write(f"price history: {getattr(res['price_model'], 'history_source', '')} "
                 f"window {getattr(res['price_model'], 'window_years', '')}\n")
        fh.write(f"options: {opts}\n")
        fh.write("limitation: trial seasons 2023-2025 only; season risk is limited to those seasons\n")
    try:
        from .report import write_charts

        write_charts(res, out)
    except ImportError:
        logger.warning("matplotlib not installed - charts skipped")
    logger.info("Investment analysis written to %s", out)
    res["output_dir"] = out
    return res
