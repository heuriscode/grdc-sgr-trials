"""Inputs for the investment analysis: trial gross margins arranged by system.

The investment analysis plugs into the existing pipeline at the crop-sequence gross
margin step (``getCropSequenceGrossMargin`` / ``getCropSequenceGrossMarginWithPrices``),
which reads ``data/processed_data``. It reads the newest gross-margin output, or a
file you name, and rebuilds every plot-year as *quantities* (tonnes of each
commodity, operating cost, material cost, urea cost) so that gross margins can be
re-priced under simulated prices and costs.

Hierarchy used throughout::

    site -> broad category -> variant (system_category) -> system id (S1.2) -> phase (P1231) -> replicate (R1)

Whole-system gross margin per hectare in a year is the mean over the system's
phases (each phase is an equal share of the rotation's area) of the replicate-mean
crop-sequence gross margin. A phase with no crop sequence sown in a year (e.g. the
fallow year of a fallow-wheat system) contributes zero, because the crop-sequence
gross margin books pre-sowing (fallow) costs to the following crop.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.utils.base_paths import get_gross_margin_data_path, get_reference_data_path

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- commodities
# Trial crop names -> commodity keys used for pricing.
CROP_ALIASES = {
    "wheat": "wheat",
    "durum": "durum",
    "durum wheat": "durum",
    "barley": "barley",
    "oat": "oats",
    "oats": "oats",
    "canola": "canola",
    "lentil": "lentil",
    "lentils": "lentil",
    "field pea": "field pea",
    "fieldpea": "field pea",
    "field peas": "field pea",
    "faba bean": "faba bean",
    "fababean": "faba bean",
    "faba beans": "faba bean",
    "chickpea": "chickpea",
    "chickpeas": "chickpea",
    "lupin": "lupin",
    "lupins": "lupin",
    "vetch": "vetch",
    # pasture species -> valued by agistment, not by yield
    "pasture": "pasture",
    "clover": "pasture",
    "sub clover": "pasture",
    "subclover": "pasture",
    "balansa clover": "pasture",
    "perennial ryegrass": "pasture",
    "chicory": "pasture",
    # cover / biomass-only species -> no direct value
    "tillage radish": "cover",
    "tillageradish": "cover",
    "warm cover mix": "cover",
    "brassica": "cover",
    "millet": "cover",
    "fallow": "cover",
    "bare ground": "cover",
}

GRAIN_COMMODITIES = [
    "wheat", "durum", "barley", "oats", "canola", "lentil",
    "field pea", "faba bean", "chickpea", "lupin", "vetch",
]
# Non-grain value channels, priced per unit of the quantity recorded:
#   hay        - tonnes of hay (oats/vetch cut in Hay systems) x (hay price - making cost)
#   agistment  - 1 unit per pasture-phase hectare x agistment value ($/ha/yr)
VALUE_CHANNELS = ["hay", "agistment"]
COMMODITIES = GRAIN_COMMODITIES + VALUE_CHANNELS

HAY_CROPS = {"oats", "vetch"}


def normalise_crop(name) -> str | None:
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return None
    s = str(name).strip().lower()
    if s in ("", "na", "nan"):
        return None
    if s not in CROP_ALIASES:
        logger.warning("Unknown crop name '%s' - treated as having no market value", name)
        return "cover"
    return CROP_ALIASES[s]


# --------------------------------------------------------------------------- loading
def latest_gross_margin_file() -> str:
    """Newest crop-sequence gross margin csv under data/outputs/gross_margins.

    Folders are named dd_mm_YYYY (optionally with a suffix such as '_priced');
    the newest folder by its date is used, preferring a '_priced' folder on the
    same date because it carries urea quantities.
    """
    root = get_gross_margin_data_path()
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    if not dirs:
        raise FileNotFoundError(f"No gross margin output folders in {root}")

    def key(d: str):
        base = d.split("_priced")[0]
        try:
            dt = pd.to_datetime(base, format="%d_%m_%Y")
        except ValueError:
            dt = pd.Timestamp(os.path.getmtime(os.path.join(root, d)), unit="s")
        return (dt, d.endswith("_priced"))

    latest = max(dirs, key=key)
    files = [f for f in os.listdir(os.path.join(root, latest)) if f.endswith(".csv")]
    if not files:
        raise FileNotFoundError(f"No csv in {os.path.join(root, latest)}")
    # file names are processed-data dates (YYYY-MM-DD.csv): newest processed data wins
    return os.path.join(root, latest, max(files))


def load_gross_margins(path: str | None = None) -> pd.DataFrame:
    path = path or latest_gross_margin_file()
    logger.info("Investment analysis reading gross margins from %s", path)
    gm = pd.read_csv(path, na_values=["NA"], keep_default_na=True)
    gm = gm.loc[:, ~gm.columns.str.startswith("Unnamed")]
    gm.attrs["source_path"] = path
    return gm


def load_system_mapping() -> pd.DataFrame:
    m = pd.read_csv(get_reference_data_path("plotSystemMapping.csv"), encoding="utf-8-sig")
    m["plot"] = m["plot"].str.strip()
    m["site"] = m["site"].str.strip().str.upper()
    m["system_category"] = m["system_category"].str.strip()
    return m


def load_broad_categories() -> pd.DataFrame:
    b = pd.read_csv(get_reference_data_path("system_broad_categories.csv"))
    b["site"] = b["site"].str.upper()
    return b


def load_site_zones() -> pd.DataFrame:
    z = pd.read_csv(get_reference_data_path("site_zones.csv"))
    z["site"] = z["site"].str.upper()
    return z


def split_plot_id(plot: pd.Series) -> pd.DataFrame:
    parts = plot.str.split("_", expand=True)
    return pd.DataFrame({"sys_id": parts[1], "phase": parts[2], "rep": parts[3]}, index=plot.index)


# --------------------------------------------------------------------------- plot-years
@dataclass
class TrialData:
    """Plot-year quantities ready for re-pricing.

    plot_years : one row per plot-year (identifiers, costs, recorded revenue/GM)
    Q          : array (n_plot_years, n_commodities) of quantities (t/ha, or 1 for agistment)
    commodities: column order of Q
    structure  : one row per site/broad/variant/sys_id/phase with the number of reps
    excluded   : plots dropped and why
    """

    plot_years: pd.DataFrame
    Q: np.ndarray
    commodities: list[str]
    structure: pd.DataFrame
    excluded: pd.DataFrame
    source_path: str


def reference_prices(price_type: str = "prices_ma5") -> pd.Series:
    """$/t by commodity from CropPriceData.csv - the prices the pipeline used for revenue."""
    cp = pd.read_csv(get_reference_data_path("CropPriceData.csv"))
    cp["commodity"] = cp["name"].map(normalise_crop)
    return cp.dropna(subset=["commodity"]).drop_duplicates("commodity").set_index("commodity")[price_type].astype(float)


def build_trial_data(gm: pd.DataFrame | None = None, revenue_basis: str = "recorded",
                     reference_price_type: str = "prices_ma5") -> TrialData:
    """Plot-year quantities for re-pricing.

    revenue_basis:
      'recorded' (default) - recorded revenue is the truth; yields only set each crop's
                 weight, i.e. quantities are scaled so yield x reference price equals
                 the recorded revenue. Recorded revenue with no priced yield becomes
                 wheat-equivalent tonnes; recorded zero revenue zeroes the yields.
      'yields'   - revenue rebuilt from the yields in the gross-margin table.
    Mismatches are listed by :func:`reconcile_revenue` either way.
    """
    if revenue_basis not in ("recorded", "yields"):
        raise ValueError("revenue_basis must be 'recorded' or 'yields'")
    gm = load_gross_margins() if gm is None else gm
    source = gm.attrs.get("source_path", "<dataframe>")
    mapping = load_system_mapping()
    broad = load_broad_categories()

    df = gm.copy()
    df["plot"] = df["plot"].str.strip()
    df = df[~df["plot"].str.contains("BUFFER", na=False)]
    df["site"] = df["site"].str.strip().str.upper()

    excluded = []
    no_year = df["year"].isna()
    if no_year.any():
        for p in df.loc[no_year, "plot"].unique():
            excluded.append({"plot": p, "reason": "no complete crop sequence in the data"})
    df = df[~no_year].copy()
    df["year"] = df["year"].astype(int)

    df = df.merge(mapping[["plot", "system_category"]], on="plot", how="left")
    unmapped = df["system_category"].isna()
    for p in df.loc[unmapped, "plot"].unique():
        excluded.append({"plot": p, "reason": "plot not in plotSystemMapping.csv"})
    df = df[~unmapped]
    df = df.merge(
        broad[["site", "system_category", "broad_category", "is_multicrop"]],
        on=["site", "system_category"],
        how="left",
    )
    if df["broad_category"].isna().any():
        missing = df.loc[df["broad_category"].isna(), ["site", "system_category"]].drop_duplicates()
        raise ValueError(
            "system categories missing from system_broad_categories.csv:\n" + missing.to_string()
        )
    df = pd.concat([df, split_plot_id(df["plot"])], axis=1)

    num = lambda c: pd.to_numeric(df.get(c, pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0)
    df["op_cost"] = num("operational_costs_dollars")
    df["mat_cost"] = num("material_input_costs_dollars")
    df["urea_cost"] = num("urea_cost_dollars") if "urea_cost_dollars" in df else 0.0
    df["revenue_recorded"] = num("plot_revenue_dollars")
    df["gm_recorded"] = num("plot_gross_margin_dollars")

    # quantities per crop-sequence row
    ci = {c: i for i, c in enumerate(COMMODITIES)}
    Qrow = np.zeros((len(df), len(COMMODITIES)))
    hay_oats = np.zeros(len(df))   # oats cut for hay: the pipeline priced these at the oat grain price
    for slot in (1, 2, 3):
        names = df[f"crop_{slot}_name"].map(normalise_crop).to_numpy()
        yields = pd.to_numeric(df[f"crop_{slot}_yield"], errors="coerce").fillna(0.0).to_numpy() / 1000.0
        hay_sys = (df["broad_category"] == "Hay").to_numpy()
        for r, (n, y) in enumerate(zip(names, yields)):
            if not isinstance(n, str) or n == "cover":
                continue
            if n == "pasture":
                Qrow[r, ci["agistment"]] = 1.0
            elif hay_sys[r] and n in HAY_CROPS:
                Qrow[r, ci["hay"]] += y
                if n == "oats":
                    hay_oats[r] += y
            else:
                Qrow[r, ci[n]] += y

    # collapse to plot-year (two sequences sown in one year are summed)
    df = df.reset_index(drop=True)
    keys = ["site", "plot", "year"]
    g = df.groupby(keys, sort=True)
    idx = g.indices
    first = g.first()[
        ["system_category", "broad_category", "is_multicrop", "sys_id", "phase", "rep"]
    ]
    sums = g[["op_cost", "mat_cost", "urea_cost", "revenue_recorded", "gm_recorded"]].sum()
    py = first.join(sums).reset_index()
    Q = np.vstack([Qrow[idx[tuple(k)]].sum(axis=0) for k in py[keys].itertuples(index=False)])
    py["agistment_flag"] = Q[:, ci["agistment"]] > 0
    Q[:, ci["agistment"]] = np.minimum(Q[:, ci["agistment"]], 1.0)
    Q_yields = Q.copy()
    hay_oats_py = np.array([hay_oats[idx[tuple(k)]].sum() for k in py[keys].itertuples(index=False)])

    # anchor quantities to recorded revenue
    ref = reference_prices(reference_price_type)
    grain_cols = [ci[c] for c in GRAIN_COMMODITIES]
    P_ref = np.array([float(ref.get(c, 0.0)) for c in GRAIN_COMMODITIES])
    V = Q[:, grain_cols] @ P_ref + hay_oats_py * float(ref.get("oats", 0.0))
    R_rec = py["revenue_recorded"].to_numpy()
    py["revenue_scale"] = 1.0
    py["revenue_wheat_equivalent_t"] = 0.0
    if revenue_basis == "recorded":
        pos = V > 0
        scale = np.ones(len(py))
        scale[pos] = R_rec[pos] / V[pos]
        for j in grain_cols + [ci["hay"]]:
            Q[pos, j] = Q[pos, j] * scale[pos]
        orphan = (~pos) & (R_rec > 0)
        Q[orphan, ci["wheat"]] += R_rec[orphan] / float(ref["wheat"])
        py["revenue_scale"] = scale
        py.loc[orphan, "revenue_wheat_equivalent_t"] = R_rec[orphan] / float(ref["wheat"])

    # rotation structure from the mapping (not the data), so missing phase-years count as zero
    struct = mapping.merge(broad[["site", "system_category", "broad_category", "is_multicrop"]],
                           on=["site", "system_category"], how="left")
    struct = pd.concat([struct, split_plot_id(struct["plot"])], axis=1)
    struct = (
        struct.groupby(["site", "broad_category", "system_category", "sys_id", "phase"])
        .agg(n_reps=("rep", "nunique"), is_multicrop=("is_multicrop", "first"))
        .reset_index()
    )
    struct = struct[struct["site"].isin(py["site"].unique())]
    td = TrialData(
        plot_years=py,
        Q=Q,
        commodities=list(COMMODITIES),
        structure=struct,
        excluded=pd.DataFrame(excluded, columns=["plot", "reason"]),
        source_path=source,
    )
    td.Q_yields = Q_yields  # type: ignore[attr-defined]
    td.revenue_basis = revenue_basis  # type: ignore[attr-defined]
    return td


def plot_year_gm(td: TrialData, prices: np.ndarray, m_op: float = 1.0, m_mat: float = 1.0,
                 m_urea: float = 1.0) -> np.ndarray:
    """Gross margin ($/ha) of every plot-year at a price vector and cost multipliers."""
    py = td.plot_years
    other_mat = (py["mat_cost"] - py["urea_cost"]).to_numpy()
    return (
        td.Q @ prices
        - py["op_cost"].to_numpy() * m_op
        - other_mat * m_mat
        - py["urea_cost"].to_numpy() * m_urea
    )


# --------------------------------------------------------------------------- variant choice
VARIANT_RULES = ("auto", "mean", "most_numerous")


def select_variants(site_struct: pd.DataFrame, broad_category: str, rule="auto") -> list[str]:
    """Pick which system categories represent a broad category at one site.

    rule:
      'auto'          most plots; ties broken towards a Mid/Medium nitrogen variant;
                      otherwise the mean of the tied variants (the default)
      'most_numerous' most plots; ties -> mean of tied variants
      'mean'          mean of all variants
      a str           that exact system_category
      a dict          {site: rule} (resolved by the caller)
    """
    sub = site_struct[site_struct["broad_category"] == broad_category]
    if sub.empty:
        return []
    counts = sub.groupby("system_category")["n_reps"].sum()  # plots = phases x reps
    if isinstance(rule, str) and rule not in VARIANT_RULES:
        if rule not in counts.index:
            raise ValueError(f"variant '{rule}' not found for {broad_category}: {list(counts.index)}")
        return [rule]
    if rule == "mean":
        return sorted(counts.index)
    top = counts[counts == counts.max()].index.tolist()
    if len(top) == 1 or rule == "most_numerous":
        return sorted(top)
    mids = [c for c in top if any(k in c.lower() for k in ("mid n", "medium"))]
    return mids[:1] if len(mids) == 1 else sorted(top)


def resolve_rule(rule, site: str):
    if isinstance(rule, dict):
        return rule.get(site, rule.get(site.lower(), "auto"))
    return rule


# --------------------------------------------------------------------------- system GMs
def phase_index(td: TrialData) -> dict:
    """{(site, system_category, sys_id, phase, year): array of plot-year row indices}."""
    py = td.plot_years
    g = py.groupby(["site", "system_category", "sys_id", "phase", "year"]).indices
    return {k: np.asarray(v) for k, v in g.items()}


def system_year_gm(td: TrialData, gm_rows: np.ndarray, baseline_rule="auto",
                   variant_rule="auto") -> pd.DataFrame:
    """Observed whole-system GM ($/ha/yr) by site, broad category and year.

    gm_rows: GM of every plot-year (from :func:`plot_year_gm`).
    Returns columns site, broad_category, year, gm, variants, and gm_vs_baseline.
    """
    pidx = phase_index(td)
    years = sorted(td.plot_years["year"].unique())
    out = []
    for site, s_struct in td.structure.groupby("site"):
        for broad, b_struct in s_struct.groupby("broad_category"):
            rule = resolve_rule(baseline_rule if broad == "Baseline" else variant_rule, site)
            variants = select_variants(s_struct, broad, rule)
            for yr in years:
                v_vals = []
                for v in variants:
                    sys_vals = []
                    for sys_id, sys_struct in b_struct[b_struct["system_category"] == v].groupby("sys_id"):
                        phases = sys_struct["phase"].tolist()
                        tot, seen = 0.0, False
                        for ph in phases:
                            rows = pidx.get((site, v, sys_id, ph, yr))
                            if rows is not None and len(rows):
                                tot += float(gm_rows[rows].mean())
                                seen = True
                        if seen:
                            sys_vals.append(tot / len(phases))
                    if sys_vals:
                        v_vals.append(np.mean(sys_vals))
                if v_vals:
                    out.append({"site": site, "broad_category": broad, "year": yr,
                                "gm": float(np.mean(v_vals)), "variants": " | ".join(variants)})
    res = pd.DataFrame(out)
    base = res[res["broad_category"] == "Baseline"][["site", "year", "gm"]].rename(columns={"gm": "baseline_gm"})
    res = res.merge(base, on=["site", "year"], how="left")
    res["gm_vs_baseline"] = res["gm"] - res["baseline_gm"]
    return res


def reconcile_revenue(td: TrialData, price_type: str = "prices_ma5", tol: float = 1.0) -> pd.DataFrame:
    """Plot-years whose recorded revenue differs from yield x reference price.

    Uses the pipeline's own reference prices (CropPriceData.csv, ``price_type``) so a
    difference points at the data (e.g. a recorded yield with no harvest revenue),
    not at the re-pricing. Hay and pasture plot-years are excluded because this
    analysis values them differently on purpose.
    """
    ref = reference_prices(price_type)
    P = np.array([float(ref.get(c, 0.0)) for c in td.commodities])
    P[td.commodities.index("hay")] = 0.0
    P[td.commodities.index("agistment")] = 0.0
    rev = getattr(td, "Q_yields", td.Q) @ P
    py = td.plot_years.assign(revenue_from_yields=rev)
    py["difference"] = py["revenue_from_yields"] - py["revenue_recorded"]
    hay_or_past = (getattr(td, "Q_yields", td.Q)[:, td.commodities.index("hay")] > 0) | py["agistment_flag"]
    out = py[(py["difference"].abs() > tol) & ~hay_or_past]
    return out[["site", "plot", "year", "broad_category", "revenue_recorded", "revenue_from_yields", "difference"]]
