"""Price and input-cost levels and their simulation.

Central prices are long-run REAL medians (base-year dollars) over a window of
recent years, so that one good or bad price year does not drive the result.

Simulation draws a joint set of relative prices for each simulated season:

  historical  (default) resample whole historical years. Each draw takes every
              commodity's real price relative to its window mean in the SAME year,
              which keeps the cross-commodity correlation (and, when input prices
              are in the history, grain-input correlation) without fitting a model.
  lognormal   multivariate lognormal with the covariance of the historical log
              relatives (useful when the history is short and smoother tails are wanted).

Input costs are scaled by multipliers on the trial's recorded costs:
  m_op    operations (contract rates, fuel)  - recorded activity costs
  m_mat   non-urea materials (chemicals, seed, other fertiliser)
  m_urea  urea
Each = level index (moves recorded costs to base-year levels) x a random relative.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.utils.base_paths import get_reference_data_path

from .config import Assumptions
from .inputs import COMMODITIES, GRAIN_COMMODITIES

logger = logging.getLogger(__name__)

PRICE_HISTORY_FILE = "price_history.csv"   # year, commodity, price_nominal_aud_t, source
CPI_FILE = "cpi_annual.csv"                # year, cpi
INPUT_SERIES = ("urea", "diesel")
PRICE_PROXIES = {"durum": "wheat", "vetch": "field pea", "faba bean": "field pea", "lupin": "field pea"}


def _read_optional(name: str) -> pd.DataFrame | None:
    path = get_reference_data_path(name)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def load_real_price_history(base_year: int) -> pd.DataFrame:
    """Wide frame: index year, columns commodity, real A$/t in base-year dollars.

    Uses price_history.csv when present, otherwise CropPriceData.csv (2019-2024).
    """
    hist = _read_optional(PRICE_HISTORY_FILE)
    if hist is not None:
        hist["commodity"] = hist["commodity"].str.strip().str.lower()
        wide = hist.pivot_table(index="year", columns="commodity", values="price_nominal_aud_t", aggfunc="mean")
        wide.attrs["source"] = PRICE_HISTORY_FILE
    else:
        cp = pd.read_csv(get_reference_data_path("CropPriceData.csv"))
        cp["name"] = cp["name"].str.strip().str.lower()
        from .inputs import normalise_crop

        cp["commodity"] = cp["name"].map(normalise_crop)
        cp = cp[cp["commodity"].isin(GRAIN_COMMODITIES)].drop_duplicates("commodity")
        cols = [c for c in cp.columns if c.startswith("prices_") and c[7:].isdigit()]
        wide = cp.set_index("commodity")[cols].T
        wide.index = [int(c[7:]) for c in cols]
        wide = wide.replace(0, np.nan)
        wide.attrs["source"] = "CropPriceData.csv"
        logger.warning("price_history.csv not found - using CropPriceData.csv (%s-%s only)",
                       wide.index.min(), wide.index.max())
    cpi = _read_optional(CPI_FILE)
    if cpi is not None:
        cpi = cpi.set_index("year")["cpi"]
        if base_year not in cpi.index:
            base = cpi.loc[cpi.index.max()]
            logger.warning("CPI has no %s value; using %s as the base", base_year, cpi.index.max())
        else:
            base = cpi.loc[base_year]
        factor = (base / cpi).reindex(wide.index)
        if factor.isna().any():
            logger.info("CPI missing for years %s - those years dropped from the real series",
                        list(factor[factor.isna()].index))
            wide = wide[factor.notna()]
            factor = factor.dropna()
        src = wide.attrs.get("source")
        wide = wide.mul(factor, axis=0)
        wide.attrs["source"] = src
        wide.attrs["real"] = True
    else:
        wide.attrs["real"] = False
        logger.warning("cpi_annual.csv not found - price history treated as already real")
    return wide.sort_index()


@dataclass
class PriceModel:
    central: np.ndarray            # per COMMODITIES, $/t (hay: net $/t; agistment: $/ha)
    hist_rel: pd.DataFrame         # year x series relative prices (grain + inputs present)
    level: dict                    # cost level indices {'op','mat','urea'}
    a: Assumptions
    scenario: str

    def draw(self, n: int, rng: np.random.Generator, method: str = "historical",
             input_shock: bool = False) -> dict:
        """n joint draws of the price vector and cost multipliers."""
        a, sc = self.a, self.scenario
        k = len(COMMODITIES)
        rel = np.ones((n, k))
        grain_cols = [c for c in GRAIN_COMMODITIES if c in self.hist_rel.columns]
        input_cols = [c for c in INPUT_SERIES if c in self.hist_rel.columns]
        cols = grain_cols + input_cols
        H = self.hist_rel[cols]
        if method == "historical":
            yrs = rng.integers(0, len(H), size=n)
            R = H.to_numpy()[yrs]
            # a series missing in the drawn year (sparse pulse records) takes an
            # independent draw from its own observed relatives, so its variability is kept
            for j in range(R.shape[1]):
                gap = np.isnan(R[:, j])
                obs = H.iloc[:, j].dropna().to_numpy()
                if gap.any():
                    R[gap, j] = rng.choice(obs, size=int(gap.sum())) if len(obs) else 1.0
        elif method == "lognormal":
            # mean-one lognormal relatives with the historical log covariance
            L = np.log(H.fillna(1.0))
            cov = np.atleast_2d(np.cov(L.to_numpy(), rowvar=False))
            Z = rng.multivariate_normal(np.zeros(len(cols)), cov, size=n)
            R = np.exp(Z - np.diag(cov) / 2)
        else:
            raise ValueError("method must be 'historical' or 'lognormal'")
        for j, c in enumerate(grain_cols):
            rel[:, COMMODITIES.index(c)] = R[:, j]
        # commodities without their own history follow a close substitute
        for c, proxy in PRICE_PROXIES.items():
            if c not in grain_cols and proxy in grain_cols:
                rel[:, COMMODITIES.index(c)] = rel[:, COMMODITIES.index(proxy)]
        # hay follows the oats relative; agistment its own lognormal
        oats = rel[:, COMMODITIES.index("oats")]
        rel[:, COMMODITIES.index("hay")] = oats
        cv_ag = a.get("prices.agistment_cv", sc)
        rel[:, COMMODITIES.index("agistment")] = _lognormal_rel(rng, cv_ag, n)
        prices = rel * self.central

        def input_rel(name: str, cv_key: str) -> np.ndarray:
            if name in input_cols:
                return R[:, len(grain_cols) + input_cols.index(name)]
            return _lognormal_rel(rng, a.get(cv_key, sc), n)

        m_urea = self.level["urea"] * input_rel("urea", "costs.urea_price_cv")
        m_op = self.level["op"] * input_rel("diesel", "costs.operations_cost_cv")
        m_mat = self.level["mat"] * _lognormal_rel(rng, a.get("costs.other_materials_cv", sc), n)
        if input_shock:
            m_urea = m_urea * a.get("costs.shock_urea_multiplier", sc)
            m_op = m_op * a.get("costs.shock_operations_multiplier", sc)
        return {"prices": prices, "m_op": m_op, "m_mat": m_mat, "m_urea": m_urea}

    def central_draw(self) -> dict:
        return {"prices": self.central[None, :], "m_op": np.array([self.level["op"]]),
                "m_mat": np.array([self.level["mat"]]), "m_urea": np.array([self.level["urea"]])}


def _lognormal_rel(rng: np.random.Generator, cv: float, n: int) -> np.ndarray:
    if cv <= 0:
        return np.ones(n)
    s2 = np.log(1 + cv ** 2)
    return np.exp(rng.normal(-s2 / 2, np.sqrt(s2), size=n))


def _has(a: Assumptions, key: str) -> bool:
    try:
        a.node(key)
        return True
    except KeyError:
        return False


def build_price_model(a: Assumptions, scenario: str = "central") -> PriceModel:
    base_year = int(a.get("meta.base_year"))
    window = int(a.get("prices.central_window_years", scenario))
    wide = load_real_price_history(base_year)
    recent = wide[wide.index > wide.index.max() - window]
    # median rather than mean: a single spike year (e.g. lentils 2016) should not set the long-run level
    stat = a.get("prices.central_statistic") if _has(a, "prices.central_statistic") else "median"
    means = recent.median() if stat == "median" else recent.mean()

    from .inputs import reference_prices

    ref_prices = reference_prices("prices_ma5")
    fallback: list[str] = []
    central = np.zeros(len(COMMODITIES))
    for i, c in enumerate(COMMODITIES):
        if c in GRAIN_COMMODITIES:
            override = f"prices.central_override.{c}"
            try:
                central[i] = a.get(override, scenario)
                continue
            except KeyError:
                pass
            v = float(means.get(c, np.nan))
            if not np.isfinite(v) or v <= 0:
                # no history (e.g. durum): fall back to the pipeline's reference price
                v = float(ref_prices.get(c, 0.0))
                if v > 0:
                    fallback.append(c)
            central[i] = v
    central[COMMODITIES.index("hay")] = (
        a.get("prices.hay_price_per_t", scenario) - a.get("prices.hay_making_cost_per_t", scenario)
    )
    central[COMMODITIES.index("agistment")] = a.get("prices.agistment_value_per_ha", scenario)
    # scenario shift on grain prices as a whole (low = weaker long-run prices)
    central[: len(GRAIN_COMMODITIES)] *= a.get("prices.grain_price_level", scenario)

    hist_rel = recent / means
    level = {
        "op": a.get("costs.operations_level_index", scenario),
        "mat": a.get("costs.other_materials_level_index", scenario),
        "urea": a.get("costs.urea_level_index", scenario),
    }
    pm = PriceModel(central=central, hist_rel=hist_rel, level=level, a=a, scenario=scenario)
    pm.window_years = sorted(recent.index.tolist())  # type: ignore[attr-defined]
    pm.history_source = wide.attrs.get("source")      # type: ignore[attr-defined]
    pm.reference_price_fallback = fallback            # type: ignore[attr-defined]
    if fallback:
        logger.info("No price history for %s - CropPriceData prices_ma5 used", fallback)
    return pm
