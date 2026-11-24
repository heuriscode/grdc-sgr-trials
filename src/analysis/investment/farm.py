"""Representative-farm investment analysis (one per agro-ecological zone).

A representative farm in a zone moves part of its crop area from the baseline
system to the tested system over an on-farm ramp, and we value the change as an
investment: incremental cash flow each year = (system GM - baseline GM) x converted
area - extra labour/management - learning losses - capital outlays + residual value.

Gross-margin differences are drawn from the system simulator: an independent
simulated season (site-year, replicate, prices, input costs) in each farm year.
Capital outlays apply only to multicropping (intercropping, companion cropping).
Hay and pasture assume the farm already holds the equipment/livestock
infrastructure (hay via contract making; pasture valued at agistment).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Assumptions
from .simulate import SystemSimulator

logger = logging.getLogger(__name__)

# broad category -> adoption/farm class used in the assumptions file
ADOPTION_CLASS = {
    "More pulses": "rotation", "Pulse-canola": "rotation", "Pulse on pulse": "rotation",
    "Alternative pulse": "rotation", "Legume-barley": "rotation", "High value broadleaf": "rotation",
    "Canola": "rotation", "More cereals": "rotation", "Continuous wheat": "rotation",
    "Winter cover cropping": "cover_crop", "Fallow": "cover_crop",
    "Intercropping": "multicrop", "Companion cropping": "multicrop",
    "Hay": "hay",
    "Pasture": "pasture", "Responsive: persistent pasture": "pasture",
    "Responsive: adviser": "responsive", "Responsive: N bank": "responsive",
    "Responsive: less chemical": "responsive", "Responsive: organic fertiliser": "responsive",
    "Responsive: soil health": "responsive",
}


def adoption_class(broad: str) -> str:
    if broad not in ADOPTION_CLASS:
        raise KeyError(f"No adoption class for broad category '{broad}' - add it to farm.ADOPTION_CLASS")
    return ADOPTION_CLASS[broad]


def discount_factors(rate: float, years: np.ndarray) -> np.ndarray:
    return (1.0 + rate) ** (-years.astype(float))


def irr_vectorised(cash: np.ndarray, lo: float = -0.95, hi: float = 5.0, iters: int = 80) -> np.ndarray:
    """IRR per row of cash (n, T) with t=1..T; NaN where no sign change."""
    t = np.arange(1, cash.shape[1] + 1, dtype=float)

    def npv(r):
        return (cash / (1 + r[:, None]) ** t).sum(axis=1)

    n = cash.shape[0]
    a, b = np.full(n, lo), np.full(n, hi)
    fa, fb = npv(a), npv(b)
    ok = np.sign(fa) != np.sign(fb)
    for _ in range(iters):
        m = (a + b) / 2
        fm = npv(m)
        left = np.sign(fm) == np.sign(fa)
        a = np.where(left, m, a)
        fa = np.where(left, fm, fa)
        b = np.where(left, b, m)
    out = (a + b) / 2
    out[~ok] = np.nan
    return out


def mirr_vectorised(cash: np.ndarray, rate: float) -> np.ndarray:
    """Modified IRR per row: negatives discounted and positives compounded at ``rate``.

    Well defined whatever the number of sign changes (unlike IRR).
    """
    n = cash.shape[1]
    t = np.arange(n, dtype=float)
    pv_neg = -(np.where(cash < 0, cash, 0.0) / (1 + rate) ** t).sum(axis=1)
    fv_pos = (np.where(cash > 0, cash, 0.0) * (1 + rate) ** (n - 1 - t)).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (fv_pos / pv_neg) ** (1.0 / (n - 1)) - 1
    out[(pv_neg <= 0) | (fv_pos <= 0)] = np.nan
    return out


def sign_changes(cash: np.ndarray) -> np.ndarray:
    s = np.sign(cash)
    s = np.where(s == 0, np.nan, s)
    out = np.zeros(cash.shape[0], dtype=int)
    for i, row in enumerate(s):
        r = row[~np.isnan(row)]
        out[i] = int((np.diff(r) != 0).sum())
    return out


def capital_schedule(a: Assumptions, cls: str, horizon: int, scenario: str) -> tuple[np.ndarray, float]:
    """(capital outlays by farm year 1..H, residual value at end of year H)."""
    capex = np.zeros(horizon)
    residual = 0.0
    if cls != "multicrop":
        return capex, residual
    items = a.get("multicrop_investment.capital_items")
    for name, item in items.items():
        cost = a.get(f"multicrop_investment.capital_items.{name}.cost", scenario)
        life = int(a.get(f"multicrop_investment.capital_items.{name}.life_years", scenario))
        for start in range(0, horizon, life):
            capex[start] += cost
        last = ((horizon - 1) // life) * life   # start index of the final purchase
        used = horizon - last
        residual += cost * max(0.0, 1 - used / life)
    return capex, residual


def farm_schedule(a: Assumptions, zone: str, cls: str, H: int, scenario: str):
    """Converted area and adoption-cost streams for farm years 1..H.

    Returns (t, converted_ha, operating_adoption_costs, capital_net_of_residual, capex, area, share).
    """
    area = a.get(f"zones.{zone}.farm_crop_area_ha", scenario)
    share = a.get(f"adoption.{cls}.farm_share_converted", scenario)
    ramp = max(1, int(a.get(f"adoption.{cls}.farm_ramp_years", scenario)))
    t = np.arange(1, H + 1)
    conv = area * share * np.minimum(1.0, t / ramp)
    new = np.diff(np.concatenate([[0.0], conv]))
    labour = a.get(f"adoption.{cls}.extra_labour_hours_per_ha", scenario) * a.get("costs.labour_rate_per_hour", scenario)
    pen = a.get(f"adoption.{cls}.learning_cost_per_ha", scenario)
    L = int(a.get(f"adoption.{cls}.learning_years", scenario))
    learning = np.array([sum(new[j] * pen for j in range(H) if 0 <= i - j < L) for i in range(H)])
    capex, residual = capital_schedule(a, cls, H, scenario)
    cap = capex.copy()
    cap[-1] -= residual
    return t, conv, labour * conv + learning, cap, capex, area, share


def farm_npv_at_mean_gain(a: Assumptions, zone: str, broad: str, mean_gain: float,
                          scenario: str = "central") -> float:
    """Deterministic farm NPV with the GM gain fixed at its long-run mean.

    Used as the adoption gate in the industry analysis: a stable expected-value test,
    unaffected by Monte Carlo noise.
    """
    cls = adoption_class(broad)
    H = int(a.get("horizons.farm_years", scenario))
    t, conv, op_costs, cap, _capex, _a, _s = farm_schedule(a, zone, cls, H, scenario)
    df = discount_factors(a.get("discounting.farm_rate", scenario), t)
    return float((mean_gain * conv - op_costs - cap) @ df)


@dataclass
class FarmResult:
    zone: str
    broad: str
    summary: dict
    npv_draws: np.ndarray
    cash_mean: np.ndarray


def farm_analysis(sim: SystemSimulator, price_model, a: Assumptions, zone: str, zone_sites: list[str],
                  broad: str, n_iter: int, rng: np.random.Generator, scenario: str = "central",
                  price_method: str = "historical", input_shock: bool = False) -> FarmResult | None:
    cls = adoption_class(broad)
    H = int(a.get("horizons.farm_years", scenario))
    need = n_iter * H
    draws = price_model.draw(int(need * 1.15) + 10, rng, method=price_method, input_shock=input_shock)
    sims = sim.simulate_zone(zone_sites, broad, draws, rng)
    if sims is None or sims.empty:
        return None
    d = sims["delta"].to_numpy()
    if len(d) < need:
        d = np.concatenate([d, rng.choice(d, size=need - len(d))])
    delta = d[:need].reshape(n_iter, H)

    t, conv, op_costs, cap, capex, area, share = farm_schedule(a, zone, cls, H, scenario)
    gm_gain = delta * conv                               # (n, H)
    cash = gm_gain - op_costs - cap

    r = a.get("discounting.farm_rate", scenario)
    df = discount_factors(r, t)
    pv_gain = gm_gain @ df
    pv_cost = float((op_costs + cap) @ df)
    npv = pv_gain - pv_cost
    annuity = df.sum()
    conv_full = area * share
    eaa_per_ha = npv / annuity / conv_full

    has_cap = capex.sum() > 0
    irr = irr_vectorised(cash) if has_cap else np.full(n_iter, np.nan)
    if has_cap:
        cum = np.cumsum(cash, axis=1)
        pay = np.where((cum >= 0).any(axis=1), (cum >= 0).argmax(axis=1) + 1, np.nan)
    else:
        pay = np.full(n_iter, np.nan)

    summary = {
        "zone": zone, "broad_category": broad, "adoption_class": cls,
        "sites": ", ".join(sorted(sims["site"].unique())),
        "farm_crop_area_ha": area, "area_converted_ha": conv_full,
        "mean_annual_gm_gain_per_ha": float(delta.mean()),
        "sd_annual_gm_gain_per_ha": float(delta.std()),
        "p_annual_gain_negative": float((delta < 0).mean()),
        "npv_mean": float(npv.mean()), "npv_p10": float(np.percentile(npv, 10)),
        "npv_p50": float(np.percentile(npv, 50)), "npv_p90": float(np.percentile(npv, 90)),
        "p_npv_positive": float((npv > 0).mean()),
        "npv_per_converted_ha_per_yr": float(eaa_per_ha.mean()),
        "pv_gm_gain_mean": float(pv_gain.mean()), "pv_adoption_costs": pv_cost,
        # BCR only where there is a capital outlay to recover; otherwise NPV is the measure
        "bcr": float(pv_gain.mean() / pv_cost) if has_cap and pv_cost > 0 else np.nan,
        "capital_outlay_initial": float(capex[0]),
        "irr_median": float(np.nanmedian(irr)) if has_cap and np.isfinite(irr).any() else np.nan,
        "payback_years_median": float(np.nanmedian(pay)) if has_cap and np.isfinite(pay).any() else np.nan,
        "p_no_payback": float(np.isnan(pay).mean()) if has_cap else np.nan,
        "discount_rate": r, "horizon_years": H, "scenario": scenario,
    }
    return FarmResult(zone, broad, summary, npv, cash.mean(axis=0))


def farm_table(results: list[FarmResult]) -> pd.DataFrame:
    return pd.DataFrame([r.summary for r in results])
