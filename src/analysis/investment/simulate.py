"""Monte Carlo simulation of whole-system gross margins.

Each simulated *season* for a zone is built from three independent draws:

  1. a trial site in the zone and a trial year at that site (the season: yields,
     operations, inputs actually used), weighted by ``seasons.year_weights``;
  2. one replicate per phase of the rotation (plot-to-plot variation);
  3. a joint set of output prices and input-cost multipliers (prices.PriceModel).

The system and its baseline are evaluated on the SAME site, year and prices in each
draw (common random numbers), so the difference isolates the system effect from the
season and the market. Replicates are drawn independently for system and baseline
because they are different plots.

Limitation stated in every output: the trial so far covers three seasons
(2023-2025). Season risk is therefore represented by those seasons only; weights
can tilt them towards the long-run rainfall distribution but cannot add seasons
the trial has not seen.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Assumptions
from .inputs import TrialData, phase_index, resolve_rule, select_variants

logger = logging.getLogger(__name__)


@dataclass
class Treatment:
    site: str
    broad: str
    # list of variants -> list of systems -> (n_phases, {phase: {year: rows}})
    variants: list


class SystemSimulator:
    def __init__(self, td: TrialData, a: Assumptions, baseline_rule="auto", variant_rule="auto"):
        self.td = td
        self.a = a
        self.baseline_rule = baseline_rule
        self.variant_rule = variant_rule
        self.pidx = phase_index(td)
        py = td.plot_years
        self.op = py["op_cost"].to_numpy()
        self.urea = py["urea_cost"].to_numpy()
        self.other_mat = (py["mat_cost"] - py["urea_cost"]).to_numpy()
        self.years = sorted(py["year"].unique())
        self._treat: dict = {}

    # ----------------------------------------------------------------- structure
    def treatment(self, site: str, broad: str) -> Treatment | None:
        key = (site, broad)
        if key in self._treat:
            return self._treat[key]
        s_struct = self.td.structure[self.td.structure["site"] == site]
        rule = resolve_rule(self.baseline_rule if broad == "Baseline" else self.variant_rule, site)
        variants = select_variants(s_struct, broad, rule)
        vlist = []
        for v in variants:
            systems = []
            for sys_id, ss in s_struct[s_struct["system_category"] == v].groupby("sys_id"):
                phases = ss["phase"].tolist()
                rows = {ph: {yr: self.pidx.get((site, v, sys_id, ph, yr)) for yr in self.years}
                        for ph in phases}
                systems.append((len(phases), rows))
            vlist.append((v, systems))
        t = Treatment(site, broad, vlist) if vlist else None
        self._treat[key] = t
        return t

    def sites_with(self, broad: str, sites: list[str]) -> list[str]:
        return [s for s in sites if self.treatment(s, broad) is not None]

    def year_weights(self, site: str) -> np.ndarray:
        w = self.a.get("seasons.year_weights")
        site_w = (w or {}).get(site) or (w or {}).get("default") or {}
        arr = np.array([float(site_w.get(y, site_w.get(str(y), 1.0))) for y in self.years])
        return arr / arr.sum()

    # ----------------------------------------------------------------- evaluation
    def _row_gm(self, rows: np.ndarray, P: np.ndarray, m_op, m_mat, m_urea) -> np.ndarray:
        return (
            np.einsum("ij,ij->i", self.td.Q[rows], P)
            - self.op[rows] * m_op
            - self.other_mat[rows] * m_mat
            - self.urea[rows] * m_urea
        )

    def evaluate(self, t: Treatment, year_arr: np.ndarray, draws: dict, rng: np.random.Generator,
                 replicate_noise: bool = True) -> np.ndarray:
        """Whole-system GM ($/ha) for each draw (all draws are at site t.site).

        year_arr: year of each draw. draws: arrays from PriceModel.draw (length n or 1).
        Returns NaN where the system has no data in the drawn year.
        """
        n = len(year_arr)
        P = np.broadcast_to(draws["prices"], (n, draws["prices"].shape[1]))
        m_op = np.broadcast_to(draws["m_op"], (n,))
        m_mat = np.broadcast_to(draws["m_mat"], (n,))
        m_urea = np.broadcast_to(draws["m_urea"], (n,))
        v_sum = np.zeros(n)
        v_cnt = np.zeros(n)
        for _v, systems in t.variants:
            s_sum = np.zeros(n)
            s_cnt = np.zeros(n)
            for n_ph, rows_by_phase in systems:
                tot = np.zeros(n)
                seen = np.zeros(n, dtype=bool)
                for ph, by_year in rows_by_phase.items():
                    for yr in self.years:
                        rows = by_year.get(yr)
                        if rows is None or len(rows) == 0:
                            continue
                        mask = year_arr == yr
                        m = int(mask.sum())
                        if m == 0:
                            continue
                        if replicate_noise:
                            pick = rng.choice(rows, size=m)
                            vals = self._row_gm(pick, P[mask], m_op[mask], m_mat[mask], m_urea[mask])
                        else:  # replicate mean
                            k = len(rows)
                            rr = np.repeat(rows[None, :], m, axis=0).ravel()
                            vals = self._row_gm(
                                rr, np.repeat(P[mask], k, axis=0), np.repeat(m_op[mask], k),
                                np.repeat(m_mat[mask], k), np.repeat(m_urea[mask], k),
                            ).reshape(m, k).mean(axis=1)
                        tot[mask] += vals
                        seen[mask] = True
                s_sum += np.where(seen, tot / n_ph, 0.0)
                s_cnt += seen
            ok = s_cnt > 0
            v_sum[ok] += s_sum[ok] / s_cnt[ok]
            v_cnt += ok
        out = np.full(n, np.nan)
        ok = v_cnt > 0
        out[ok] = v_sum[ok] / v_cnt[ok]
        return out

    # ----------------------------------------------------------------- zone draws
    def simulate_zone(self, zone_sites: list[str], broad: str, draws: dict, rng: np.random.Generator,
                      replicate_noise: bool = True) -> pd.DataFrame | None:
        """Simulated seasons for one system and the baseline in a zone.

        The zone's season is a uniformly chosen site (among sites that tested the
        system) and a weighted year at that site. Returns a frame with columns
        site, year, gm_system, gm_baseline, delta - or None if not tested in the zone.
        """
        sites = [s for s in self.sites_with(broad, zone_sites) if self.treatment(s, "Baseline")]
        if not sites:
            return None
        n = draws["prices"].shape[0]
        site_pick = rng.integers(0, len(sites), size=n)
        year_arr = np.empty(n, dtype=int)
        sys_gm = np.full(n, np.nan)
        base_gm = np.full(n, np.nan)
        for i, s in enumerate(sites):
            mask = site_pick == i
            m = int(mask.sum())
            if m == 0:
                continue
            yrs = rng.choice(self.years, size=m, p=self.year_weights(s))
            year_arr[mask] = yrs
            sub = {k: (v[mask] if np.ndim(v) and len(v) == n else v) for k, v in draws.items()}
            sys_gm[mask] = self.evaluate(self.treatment(s, broad), yrs, sub, rng, replicate_noise)
            base_gm[mask] = self.evaluate(self.treatment(s, "Baseline"), yrs, sub, rng, replicate_noise)
        df = pd.DataFrame({"site": np.array(sites)[site_pick], "year": year_arr,
                           "gm_system": sys_gm, "gm_baseline": base_gm})
        df["delta"] = df["gm_system"] - df["gm_baseline"]
        dropped = df["delta"].isna().mean()
        if dropped > 0:
            logger.info("%s: %.1f%% of draws fell in a year without data and were dropped", broad, 100 * dropped)
        return df.dropna(subset=["delta"]).reset_index(drop=True)

    # ----------------------------------------------------------------- evidence
    def bootstrap_mean_delta(self, sites: list[str], broad: str, central: dict, B: int,
                             rng: np.random.Generator, combine: str = "mean") -> np.ndarray:
        """Bootstrap distribution of the MEAN annual GM difference vs baseline.

        Resamples trial years (with replacement) and replicates at each site, at
        central prices, then averages over sites. This is the uncertainty about the
        long-run average benefit - used for the industry and project analysis and
        for the trial-evidence table (which replaces system_baseline_comparisons).
        """
        sites = [s for s in sites if self.treatment(s, broad) and self.treatment(s, "Baseline")]
        if not sites:
            return np.array([])
        per_site = []
        for s in sites:
            t_sys, t_base = self.treatment(s, broad), self.treatment(s, "Baseline")
            yrs = rng.choice(self.years, size=(B, len(self.years)), p=self.year_weights(s)).ravel()
            d = self.evaluate(t_sys, yrs, central, rng) - self.evaluate(t_base, yrs, central, rng)
            d = d.reshape(B, len(self.years))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN rows: no data in drawn years
                per_site.append(np.nanmean(d, axis=1))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            stack = np.vstack(per_site)
            if combine == "best_site":
                # comparison scenario only: credit the zone with its best-performing site
                best = int(np.nanargmax(np.nanmean(stack, axis=1)))
                out = stack[best]
            else:
                out = np.nanmean(stack, axis=0)
        return out[np.isfinite(out)]
