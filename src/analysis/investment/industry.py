"""Industry (regional) and project-level benefit-cost analysis.

Industry benefit of a system in a zone, year t:
    zone crop area x adoption share(t) x net benefit per adopted ha
where net benefit per ha = long-run mean GM gain over baseline (bootstrap of trial
years and replicates at central prices) - extra labour - learning (one-off per newly
adopting ha) - annualised capital (multicropping only, spread over the farm's
converted area).

Adoption follows a logistic curve (ADOPT convention: 'years to peak' = time from
first adoption to ~99% of the ceiling), starting after a lag, with dis-adoption at
a constant annual rate after the peak. The long-run gain per ha is drawn from the
(shrunk, see shrink_gains) bootstrap of the trial evidence, losses included. Adoption
is credited only where the representative farm's expected NPV at the shrunk mean gain
is positive. By default (``evidence_weighting``) the adoption ceiling is also scaled by
the CONFIDENCE that the system beats its baseline: the share of bootstrap resamples of
the trial data (trial years and replicate plots drawn with replacement) in which the
system's average gross margin exceeds the baseline's. An optional hard threshold (``adoption.evidence_threshold``, off at 0.5)
is a stress test: no adoption unless the bootstrap probability of a positive gain
reaches it.

Project benefit is NOT the whole adoption curve. Following the evidence that
extension mostly brings adoption forward rather than raising its ceiling (Marsh,
Pannell & Lindner 2000), the without-project curve is the same curve delayed by
``project.adoption_advance_years`` and scaled by ``project.counterfactual_ceiling_share``.
The project is credited with the gap between the two curves, multiplied by the
probability that the research delivers a usable result and an attribution share
for the other programmes and groups working on the same practices.

Costs are the research investment (GRDC + co-investment), real, compounded to the
base year at the public discount rate for years already past.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .config import Assumptions
from .farm import adoption_class

logger = logging.getLogger(__name__)


def logistic_adoption(years: np.ndarray, ceiling: float, start: float, years_to_peak: float,
                      disadoption: float = 0.0) -> np.ndarray:
    """Share of area adopted in each calendar year (vectorised over draws if args are arrays).

    1% of ceiling at ``start``, 99% at ``start + years_to_peak``; after the peak year
    the share declines by ``disadoption`` per year.
    """
    years = np.asarray(years, dtype=float)
    ceiling, start, ytp, dis = (np.asarray(x, dtype=float)[..., None] for x in (ceiling, start, years_to_peak, disadoption))
    k = 2 * np.log(99) / np.maximum(ytp, 1e-9)
    mid = start + ytp / 2
    share = ceiling / (1 + np.exp(-k * (years - mid)))
    share = np.where(years < start, 0.0, share)
    peak = start + ytp
    after = years > peak
    decay = (1 - dis) ** np.maximum(years - peak, 0)
    return np.where(after, ceiling * 0.99 * decay, share)


def shrink_gains(zone_deltas: dict) -> tuple[dict, pd.DataFrame]:
    """Empirical-Bayes shrinkage of each system's mean gain towards zero.

    Each (zone, system) has a bootstrap distribution of its mean gain: estimate m_k with
    sampling variance v_k. True effects are assumed to vary across systems with variance
    tau^2 around zero (method of moments: tau^2 = max(0, var(m_k) - mean(v_k))). The
    posterior mean is B_k m_k with B_k = tau^2 / (tau^2 + v_k): a noisy estimate from one
    site and three seasons is pulled strongly towards zero; a precise one barely moves.
    Draws are mapped to B_k m_k + sqrt(B_k) (d - m_k) so the spread shrinks consistently.
    """
    keys = [k for k, d in zone_deltas.items() if len(d) > 1]
    if len(keys) < 3:
        return zone_deltas, pd.DataFrame()
    m = np.array([np.mean(zone_deltas[k]) for k in keys])
    v = np.array([np.var(zone_deltas[k]) for k in keys])
    tau2 = max(0.0, float(np.var(m) - np.mean(v)))
    out, rows = dict(zone_deltas), []
    for k, mk, vk in zip(keys, m, v):
        B = tau2 / (tau2 + vk) if (tau2 + vk) > 0 else 0.0
        d = zone_deltas[k]
        out[k] = B * mk + np.sqrt(B) * (d - mk)
        rows.append({"zone": k[0], "broad_category": k[1], "raw_mean_gain": mk, "raw_se": np.sqrt(vk),
                     "shrink_factor": B, "shrunk_mean_gain": B * mk, "tau": np.sqrt(tau2)})
    return out, pd.DataFrame(rows)


def triangular(rng: np.random.Generator, lo: float, mode: float, hi: float, n: int) -> np.ndarray:
    if hi <= lo:
        return np.full(n, mode)
    return rng.triangular(lo, mode, hi, size=n)


def research_costs(a: Assumptions, scenario: str) -> pd.Series:
    """Real research cost by calendar year."""
    total = a.get("project.research_cost_total", scenario)
    first, last = int(a.get("project.first_investment_year")), int(a.get("project.last_investment_year"))
    yrs = np.arange(first, last + 1)
    return pd.Series(total / len(yrs), index=yrs)


def industry_analysis(a: Assumptions, zone_deltas: dict, farm_npv_central: dict, n_draws: int,
                      rng: np.random.Generator, scenario: str = "central", confidence: dict | None = None, evidence_weighting: bool = True,
                      reallocate: bool = True, cap_at_class_high: bool = False) -> dict:
    """Industry and project BCA by Monte Carlo.

    zone_deltas: {(zone, broad): bootstrap draws of the mean annual GM gain ($/ha)}
    farm_npv_central: {(zone, broad): farm NPV at the (shrunk) mean gain} - the adoption gate
    """
    base = int(a.get("meta.base_year"))
    first = int(a.get("project.first_investment_year"))
    last = int(a.get("project.last_investment_year"))
    end = last + int(a.get("horizons.project_years_after_investment"))
    years = np.arange(first, end + 1)
    r_pub = a.get("discounting.public_rate", scenario)
    disc = (1 + r_pub) ** (-(years - base).astype(float))   # past years compound forward

    p_success = triangular(rng, *a.triple("project.probability_of_success"), n_draws)
    attribution = triangular(rng, *a.triple("project.attribution_share"), n_draws)
    advance = triangular(rng, *a.triple("project.adoption_advance_years"), n_draws)
    cf_ceiling = triangular(rng, *a.triple("project.counterfactual_ceiling_share"), n_draws)
    adoption_start = int(a.get("project.adoption_start_year"))
    joint_cap = a.get("adoption.joint_cap_share", scenario)

    evidence_threshold = a.get("adoption.evidence_threshold", scenario)
    gate_reason, p_gain, p_adopt = {}, {}, {}
    rows = []
    gross_by_key, proj_by_key, share_by_key = {}, {}, {}
    zones = sorted({z for z, _ in zone_deltas})
    zone_area = {z: triangular(rng, *a.triple(f"zones.{z}.crop_area_ha"), n_draws) for z in zones}

    # ---- pass 1: per system draws, adoption gate and confidence
    sysd = {}
    for (zone, broad), deltas in zone_deltas.items():
        cls = adoption_class(broad)
        if broad == "Baseline" or len(deltas) == 0:
            continue
        # confidence: share of bootstrap resamples of the trial data (years and replicates)
        # in which the system's average gross margin beats the baseline - computed on the
        # raw, unshrunk evidence when supplied
        p_pos = float(confidence[(zone, broad)]) if confidence and (zone, broad) in confidence \
            else float(np.mean(deltas > 0))
        evidence_ok = p_pos >= evidence_threshold
        ceiling = triangular(rng, *a.triple(f"adoption.{cls}.ceiling_share"), n_draws)
        ytp = triangular(rng, *a.triple(f"adoption.{cls}.years_to_peak"), n_draws)
        lag = triangular(rng, *a.triple(f"adoption.{cls}.lag_years"), n_draws)
        dis = triangular(rng, *a.triple(f"adoption.{cls}.disadoption_rate"), n_draws)

        # net benefit per adopted ha: a draw of the long-run mean gain (trial evidence)
        gain = rng.choice(deltas, size=n_draws)
        labour = a.get(f"adoption.{cls}.extra_labour_hours_per_ha", scenario) * a.get("costs.labour_rate_per_hour", scenario)
        conv_ha = a.get(f"zones.{zone}.farm_crop_area_ha", scenario) * a.get(f"adoption.{cls}.farm_share_converted", scenario)
        cap_per_ha = 0.0
        if cls == "multicrop":
            for name in a.get("multicrop_investment.capital_items"):
                cost = a.get(f"multicrop_investment.capital_items.{name}.cost", scenario)
                life = a.get(f"multicrop_investment.capital_items.{name}.life_years", scenario)
                crf = r_pub / (1 - (1 + r_pub) ** (-life)) if r_pub > 0 else 1 / life
                cap_per_ha += cost * crf / conv_ha
        learn_once = a.get(f"adoption.{cls}.learning_cost_per_ha", scenario) * a.get(f"adoption.{cls}.learning_years", scenario)
        net = gain - labour - cap_per_ha                           # (n,)

        # Adoption gate: expected farm NPV (at the shrunk mean gain) must be positive,
        # and - as an optional stress test - the evidence threshold met. Benefits then
        # use the full distribution of the gain (losses included), so no upside-only bias.
        gate = farm_npv_central.get((zone, broad), np.nan)
        adopt = bool(np.isfinite(gate) and gate > 0 and evidence_ok)
        p_gain[(zone, broad)] = p_pos
        p_adopt[(zone, broad)] = float(adopt)
        gate_reason[(zone, broad)] = (
            "adopted" if adopt
            else "expected farm NPV not positive" if not (np.isfinite(gate) and gate > 0)
            else f"evidence below threshold (P(gain>0)={p_pos:.2f} < {evidence_threshold:.2f})"
        )
        sysd[(zone, broad)] = dict(ceiling_raw=ceiling, ytp=ytp, lag=lag, dis=dis, net=net,
                                   learn_once=learn_once, adopt=adopt, p_pos=p_pos,
                                   mean_net=float(np.mean(net)))

    # ---- pass 2: adoption ceilings per zone
    alloc_rows = []
    for zone in zones:
        keys = [k for k in sysd if k[0] == zone]
        if not keys:
            continue
        better = [k for k in keys if sysd[k]["adopt"]]
        if reallocate:
            # Systems compete for the same paddocks. The zone's potential adoption area -
            # the ceilings of ALL systems tested there, capped jointly - goes to the better
            # systems only, shared in proportion to expected net gain x confidence
            # (confidence only if evidence_weighting). Weaker systems get none.
            pool = np.minimum(sum(sysd[k]["ceiling_raw"] for k in keys), joint_cap)
            w = {k: max(sysd[k]["mean_net"], 0.0) * (sysd[k]["p_pos"] if evidence_weighting else 1.0)
                 for k in better}
            wsum = sum(w.values())
            for k in keys:
                share = w.get(k, 0.0) / wsum if wsum > 0 else 0.0
                c = pool * share
                if cap_at_class_high:
                    # no system may exceed the HIGH ceiling of its own adoption class
                    c = np.minimum(c, a.triple(f"adoption.{adoption_class(k[1])}.ceiling_share")[2])
                sysd[k]["ceiling"] = c
                alloc_rows.append({"zone": zone, "broad_category": k[1], "allocation_weight": share})
        else:
            for k in keys:
                c = sysd[k]["ceiling_raw"] * (sysd[k]["p_pos"] if evidence_weighting else 1.0)
                sysd[k]["ceiling"] = c if sysd[k]["adopt"] else np.zeros(n_draws)

    # ---- pass 3: adoption curves and benefits
    for (zone, broad), d in sysd.items():
        area = zone_area[zone]
        ceiling = d["ceiling"]
        with_p = logistic_adoption(years, ceiling, adoption_start + d["lag"], d["ytp"], d["dis"])
        without_p = logistic_adoption(years, ceiling * cf_ceiling, adoption_start + d["lag"] + advance, d["ytp"], d["dis"])

        def benefits(share, net=d["net"], learn_once=d["learn_once"]):
            adopted = area[:, None] * share
            new = np.clip(np.diff(adopted, axis=1, prepend=0.0), 0, None)
            return adopted * net[:, None] - new * learn_once

        gross = benefits(with_p)
        proj = (gross - benefits(without_p)) * (p_success * attribution)[:, None]
        gross_by_key[(zone, broad)] = gross
        proj_by_key[(zone, broad)] = proj
        share_by_key[(zone, broad)] = with_p

    # joint cap (when not reallocating): systems compete for the same paddocks
    if not reallocate:
        for zone in zones:
            keys = [k for k in share_by_key if k[0] == zone]
            if not keys:
                continue
            total = sum(share_by_key[k] for k in keys)
            scale = np.where(total > joint_cap, joint_cap / np.maximum(total, 1e-12), 1.0)
            for k in keys:
                gross_by_key[k] = gross_by_key[k] * scale
                proj_by_key[k] = proj_by_key[k] * scale
                share_by_key[k] = share_by_key[k] * scale

    for (zone, broad), gross in gross_by_key.items():
        proj = proj_by_key[(zone, broad)]
        pv_g, pv_p = gross @ disc, proj @ disc
        peak_ha = (share_by_key[(zone, broad)] * 1.0).max(axis=1)
        rows.append({
            "zone": zone, "broad_category": broad, "adoption_class": adoption_class(broad),
            "farm_npv_central": farm_npv_central.get((zone, broad), np.nan),
            "adopted": bool(np.any(peak_ha > 0)),
            "adoption_gate": gate_reason.get((zone, broad), ""),
            "confidence_beats_baseline": p_gain.get((zone, broad), np.nan),
            "mean_gm_gain_per_ha": float(np.mean(zone_deltas[(zone, broad)])),
            "adoption_ceiling_share_mean": float(np.mean(sysd[(zone, broad)]["ceiling"])),
            "peak_adoption_share_mean": float(peak_ha.mean()),
            "pv_industry_benefit_mean": float(pv_g.mean()),
            "pv_industry_benefit_p10": float(np.percentile(pv_g, 10)),
            "pv_industry_benefit_p90": float(np.percentile(pv_g, 90)),
            "pv_project_benefit_mean": float(pv_p.mean()),
            "pv_project_benefit_p10": float(np.percentile(pv_p, 10)),
            "pv_project_benefit_p90": float(np.percentile(pv_p, 90)),
        })
    table = pd.DataFrame(rows)

    # project totals
    costs = research_costs(a, scenario).reindex(years, fill_value=0.0).to_numpy()
    pv_cost = float(costs @ disc)
    proj_total = sum(proj_by_key.values()) if proj_by_key else np.zeros((n_draws, len(years)))
    gross_total = sum(gross_by_key.values()) if gross_by_key else np.zeros((n_draws, len(years)))
    pv_b = proj_total @ disc
    npv = pv_b - pv_cost
    cash = proj_total - costs[None, :]
    from .farm import irr_vectorised

    from .farm import mirr_vectorised, sign_changes

    # IRR only where the cash flow changes sign once (otherwise it is ambiguous: when the
    # project brings adoption forward and adoption later declines, net benefits turn
    # negative late); MIRR at the public rate is always defined
    irr = irr_vectorised(cash)
    irr[sign_changes(cash) != 1] = np.nan
    mirr = mirr_vectorised(cash, r_pub)
    project = {
        "scenario": scenario, "base_year": base, "first_year": first, "last_year": end,
        "public_discount_rate": r_pub, "pv_research_cost": pv_cost,
        "pv_industry_benefit_mean": float((gross_total @ disc).mean()),
        "pv_project_benefit_mean": float(pv_b.mean()),
        "pv_project_benefit_p10": float(np.percentile(pv_b, 10)),
        "pv_project_benefit_p90": float(np.percentile(pv_b, 90)),
        "npv_mean": float(npv.mean()), "npv_p10": float(np.percentile(npv, 10)),
        "npv_p90": float(np.percentile(npv, 90)),
        "bcr_mean": float(pv_b.mean() / pv_cost) if pv_cost else np.nan,
        "bcr_p10": float(np.percentile(pv_b / pv_cost, 10)) if pv_cost else np.nan,
        "bcr_p90": float(np.percentile(pv_b / pv_cost, 90)) if pv_cost else np.nan,
        "p_npv_positive": float((npv > 0).mean()),
        "irr_median": float(np.nanmedian(irr)) if np.isfinite(irr).any() else np.nan,
        "irr_defined_share": float(np.isfinite(irr).mean()),
        "mirr_median": float(np.nanmedian(mirr)) if np.isfinite(mirr).any() else np.nan,
    }
    annual = pd.DataFrame({
        "year": years, "research_cost": costs,
        "industry_benefit_mean": gross_total.mean(axis=0),
        "project_benefit_mean": proj_total.mean(axis=0),
        "discount_factor": disc,
    })
    return {"table": table, "project": project, "annual": annual}
