"""Charts for the investment analysis (matplotlib, written as PNG)."""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _cdf_plot(sims: dict, zone: str, path: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    base_done = False
    for (z, broad), s in sorted(sims.items()):
        if z != zone:
            continue
        x = np.sort(s["gm_system"].to_numpy())
        ax.plot(x, np.linspace(0, 1, len(x)), lw=1.2, label=broad)
        if not base_done:
            b = np.sort(s["gm_baseline"].to_numpy())
            ax.plot(b, np.linspace(0, 1, len(b)), lw=2.2, color="black", label="Baseline")
            base_done = True
    ax.set_xlabel("Whole-system gross margin ($/ha/yr, simulated)")
    ax.set_ylabel("Cumulative probability")
    ax.set_title(f"{zone}: distribution of annual gross margin")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _serf_plot(serf_df, zone: str, path: str) -> None:
    sub = serf_df[serf_df["zone"] == zone]
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for broad, g in sub.groupby("system"):
        ax.plot(g["rr"], g["risk_premium_vs_baseline"], label=broad)
    ax.axhline(0, color="black", lw=1)
    ax.set_xlabel("Relative risk aversion (0 = neutral, 4 = extremely averse)")
    ax.set_ylabel("Certainty-equivalent gain over baseline ($/ha/yr)")
    ax.set_title(f"{zone}: SERF")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _tornado(sens, path: str) -> None:
    if sens is None or sens.empty:
        return
    piv = sens.pivot(index="parameter", columns="case", values="npv")
    centre = piv.mean(axis=1)
    order = (piv["high"] - piv["low"]).abs().sort_values().index
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, p in enumerate(order):
        lo, hi = piv.loc[p, "low"], piv.loc[p, "high"]
        ax.barh(i, hi - lo, left=lo, color="#4C72B0" if hi >= lo else "#DD8452")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=7)
    ax.axvline(float(centre.median()), color="black", lw=1)
    ax.set_xlabel("Project NPV ($, low to high value of each parameter)")
    ax.set_title("Sensitivity of project NPV")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_charts(res: dict, out: str) -> None:
    zones = sorted({z for z, _ in res.get("simulations", {})})
    for z in zones:
        _cdf_plot(res["simulations"], z, os.path.join(out, f"cdf_{z}.png"))
        if not res["serf"].empty:
            _serf_plot(res["serf"], z, os.path.join(out, f"serf_{z}.png"))
    _tornado(res.get("sensitivity"), os.path.join(out, "tornado_project_npv.png"))
