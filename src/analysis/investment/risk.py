"""Risk ranking of systems: stochastic dominance, SERF and summary risk measures.

Why risk preferences appear at all
----------------------------------
A mean gross margin says nothing about how often a system loses money. Stochastic
dominance ranks whole distributions with as few assumptions about the farmer as
possible:

* First-order (FSD): A dominates B if A's cumulative distribution is never above
  B's - every farmer who prefers more money to less prefers A, whatever their
  attitude to risk. No risk assumption needed.
* Second-order (SSD): A dominates B if the area under A's CDF is never above B's at
  any point - every farmer who prefers more AND is risk-averse prefers A.
  If neither dominates, the ranking genuinely depends on the farmer.
* SERF (stochastic efficiency with respect to a function; Hardaker et al. 2004)
  fills that gap: it reports each system's certainty equivalent (the sure $/ha a
  farmer would swap the risky outcome for) across a range of relative risk
  aversion from 0 (risk-neutral: ranks by the mean) to 4 (extremely averse), using
  constant relative risk aversion on wealth (Hardaker 2010). Where the ranking does
  not change across the range, risk preference does not matter for the advice.

The dominance tests run on (a) simulated annual whole-system GM and (b) the
trial observations (site-year system GMs) with the Barrett & Donald (2003)
bootstrap test - the latter has low power with three seasons and says so.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ dominance
def _grid(x: np.ndarray, y: np.ndarray, n: int = 512) -> np.ndarray:
    lo, hi = min(x.min(), y.min()), max(x.max(), y.max())
    return np.linspace(lo, hi, n)


def _cdf(x: np.ndarray, z: np.ndarray) -> np.ndarray:
    xs = np.sort(x)
    return np.searchsorted(xs, z, side="right") / len(xs)


def _integrated_cdf(x: np.ndarray, z: np.ndarray) -> np.ndarray:
    # E[(z - X)+] = integral of the CDF up to z
    return np.maximum(z[:, None] - x[None, :], 0).mean(axis=1)


def dominance(x: np.ndarray, y: np.ndarray, tol: float = 1e-3) -> dict:
    """Descriptive FSD/SSD of x over y (and y over x) on empirical distributions.

    tol: allowed CDF crossing (share of probability for FSD; $/ha for SSD scaled by
    range) to absorb Monte Carlo noise.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    z = _grid(x, y)
    Fx, Fy = _cdf(x, z), _cdf(y, z)
    Ix, Iy = _integrated_cdf(x, z), _integrated_cdf(y, z)
    scale = max(z[-1] - z[0], 1e-9)
    fsd_xy = bool(np.all(Fx <= Fy + tol) and np.any(Fx < Fy - tol))
    fsd_yx = bool(np.all(Fy <= Fx + tol) and np.any(Fy < Fx - tol))
    ssd_xy = bool(np.all(Ix <= Iy + tol * scale) and np.any(Ix < Iy - tol * scale))
    ssd_yx = bool(np.all(Iy <= Ix + tol * scale) and np.any(Iy < Ix - tol * scale))
    if fsd_xy:
        verdict = "FSD"
    elif ssd_xy:
        verdict = "SSD"
    elif fsd_yx:
        verdict = "dominated (FSD)"
    elif ssd_yx:
        verdict = "dominated (SSD)"
    else:
        verdict = "no dominance"
    return {"fsd": fsd_xy, "ssd": ssd_xy, "fsd_reverse": fsd_yx, "ssd_reverse": ssd_yx, "verdict": verdict}


def barrett_donald(x: np.ndarray, y: np.ndarray, order: int = 1, B: int = 999,
                   rng: np.random.Generator | None = None) -> float:
    """Bootstrap p-value for H0: x dominates y at the given order (1 or 2).

    Small p rejects dominance. Barrett & Donald (2003, Econometrica 71:71-104),
    pooled-sample bootstrap (least-favourable null).
    """
    rng = rng or np.random.default_rng(0)
    x, y = np.asarray(x, float), np.asarray(y, float)
    n, m = len(x), len(y)
    if n < 2 or m < 2:
        return np.nan
    z = _grid(x, y, 256)
    D = _cdf if order == 1 else _integrated_cdf

    def stat(a, b):
        return np.sqrt(n * m / (n + m)) * np.max(D(a, z) - D(b, z))

    s = stat(x, y)
    pooled = np.concatenate([x, y])
    exceed = 0
    for _ in range(B):
        a = rng.choice(pooled, n)
        b = rng.choice(pooled, m)
        exceed += stat(a, b) >= s
    return (exceed + 1) / (B + 1)


# ------------------------------------------------------------------ SERF
def certainty_equivalent(x: np.ndarray, rr: float, wealth: float) -> float:
    """CE ($ relative to wealth) under CRRA utility on wealth + x."""
    w = wealth + np.asarray(x, float)
    if np.any(w <= 0):
        w = np.maximum(w, 1e-6 * wealth)  # wipe-out outcomes floored (flagged by p_loss)
    if rr == 0:
        return float(w.mean() - wealth)
    if abs(rr - 1) < 1e-9:
        return float(np.exp(np.log(w).mean()) - wealth)
    eu = np.mean(w ** (1 - rr))
    return float(eu ** (1 / (1 - rr)) - wealth)


def serf(dists: dict, wealth: float, rr_grid=None) -> pd.DataFrame:
    rr_grid = np.linspace(0, 4, 17) if rr_grid is None else rr_grid
    rows = []
    for name, x in dists.items():
        for rr in rr_grid:
            rows.append({"system": name, "rr": float(rr), "ce": certainty_equivalent(x, rr, wealth)})
    df = pd.DataFrame(rows)
    if "Baseline" in dists:
        base = df[df["system"] == "Baseline"].set_index("rr")["ce"]
        df["risk_premium_vs_baseline"] = df["ce"] - df["rr"].map(base)
    return df


# ------------------------------------------------------------------ summaries
def risk_stats(x: np.ndarray) -> dict:
    x = np.asarray(x, float)
    p10 = np.percentile(x, 10)
    mean = x.mean()
    return {
        "mean": float(mean), "sd": float(x.std()),
        "cv": float(x.std() / abs(mean)) if mean else np.nan,
        "p10": float(p10), "p50": float(np.percentile(x, 50)), "p90": float(np.percentile(x, 90)),
        "p_loss": float((x < 0).mean()),
        "cvar10": float(x[x <= p10].mean()) if (x <= p10).any() else float(p10),
    }
