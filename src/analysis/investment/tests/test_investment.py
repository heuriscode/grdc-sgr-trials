"""Tests for the investment analysis. Run from the repo root: python -m pytest src/analysis/investment/tests"""

import os

import numpy as np
import pandas as pd
import pytest
import yaml

from src.analysis.investment.config import Assumptions
from src.analysis.investment.farm import capital_schedule, irr_vectorised
from src.analysis.investment.industry import logistic_adoption
from src.analysis.investment.inputs import select_variants
from src.analysis.investment.risk import barrett_donald, certainty_equivalent, dominance, serf

REPO_FILES = os.path.exists(os.path.join("data", "reference_data", "investment_assumptions.yaml"))


# ------------------------------------------------------------------ assumptions
def test_uncited_parameter_is_refused(tmp_path):
    p = tmp_path / "a.yaml"
    p.write_text(yaml.safe_dump({"x": {"central": 1.0}}))
    with pytest.raises(ValueError, match="missing 'source'"):
        Assumptions.load(str(p))


def test_out_of_order_range_is_refused(tmp_path):
    p = tmp_path / "a.yaml"
    p.write_text(yaml.safe_dump({"x": {"central": 1.0, "low": 2.0, "high": 3.0, "source": "s", "status": "judgement"}}))
    with pytest.raises(ValueError, match="low <= central <= high"):
        Assumptions.load(str(p))


def test_scenarios_and_overrides(tmp_path):
    p = tmp_path / "a.yaml"
    p.write_text(yaml.safe_dump({"r": {"central": 0.05, "low": 0.03, "high": 0.07, "source": "s", "status": "verified"}}))
    a = Assumptions.load(str(p))
    assert a.get("r") == 0.05 and a.get("r", "low") == 0.03 and a.get("r", "high") == 0.07
    assert a.with_overrides(r=0.1).get("r") == 0.1
    assert a.register()[0]["source"] == "s"


@pytest.mark.skipif(not REPO_FILES, reason="run from the repo root")
def test_repo_assumptions_file_is_valid():
    a = Assumptions.load()
    assert all(r["source"] for r in a.register())


# ------------------------------------------------------------------ variant rules
def _struct(counts):
    return pd.DataFrame([{"broad_category": "Baseline", "system_category": k, "n_reps": v} for k, v in counts.items()])


def test_variant_auto_prefers_most_numerous():
    s = _struct({"Baseline (Low N)": 3, "Baseline (Mid N)": 9})
    assert select_variants(s, "Baseline", "auto") == ["Baseline (Mid N)"]


def test_variant_auto_tie_goes_to_mid_n_else_mean():
    s = _struct({"Baseline (SDP N)": 9, "Baseline (Mid N)": 9, "Baseline (High N)": 9})
    assert select_variants(s, "Baseline", "auto") == ["Baseline (Mid N)"]
    s2 = _struct({"Baseline (Dec 2 N)": 6, "Baseline (Dec 7 N)": 6})
    assert select_variants(s2, "Baseline", "auto") == ["Baseline (Dec 2 N)", "Baseline (Dec 7 N)"]


def test_variant_explicit_and_mean():
    s = _struct({"Baseline (Low N)": 3, "Baseline (Mid N)": 9})
    assert select_variants(s, "Baseline", "Baseline (Low N)") == ["Baseline (Low N)"]
    assert len(select_variants(s, "Baseline", "mean")) == 2
    with pytest.raises(ValueError):
        select_variants(s, "Baseline", "Baseline (Nope)")


# ------------------------------------------------------------------ adoption
def test_logistic_adoption_shape():
    years = np.arange(2028, 2060)
    a = logistic_adoption(years, 0.1, 2030, 10, 0.0).ravel()
    assert a[years < 2030].sum() == 0
    assert a[years == 2030][0] == pytest.approx(0.001, rel=0.05)      # 1% of ceiling at start
    assert a[years == 2040][0] == pytest.approx(0.099, rel=0.01)      # ~99% at start + years to peak
    assert np.all(a <= 0.1 + 1e-12)


def test_disadoption_declines_after_peak():
    years = np.arange(2028, 2060)
    a = logistic_adoption(years, 0.1, 2030, 10, 0.05).ravel()
    after = a[years > 2040]
    assert np.all(np.diff(after) < 0)


# ------------------------------------------------------------------ finance
def test_irr_known_value():
    cash = np.array([[-100.0, 0, 0, 0, 0, 0, 0, 0, 0, 0]])
    cash[0, 1:] = 20  # -100 then 9 x 20
    r = irr_vectorised(cash)[0]
    t = np.arange(1, 11)
    assert (cash[0] / (1 + r) ** t).sum() == pytest.approx(0, abs=1e-6)


def test_irr_nan_without_sign_change():
    assert np.isnan(irr_vectorised(np.ones((1, 5)))[0])


def test_capital_schedule_replacement_and_residual(tmp_path):
    tree = {"multicrop_investment": {"capital_items": {"kit": {
        "cost": {"central": 100.0, "source": "s", "status": "judgement"},
        "life_years": {"central": 8, "source": "s", "status": "judgement"}}}}}
    p = tmp_path / "a.yaml"
    p.write_text(yaml.safe_dump(tree))
    capex, residual = capital_schedule(Assumptions.load(str(p)), "multicrop", 20, "central")
    assert capex[0] == 100 and capex[8] == 100 and capex[16] == 100 and capex.sum() == 300
    assert residual == pytest.approx(100 * (1 - 4 / 8))   # bought in year 17, used 4 of 8 years
    capex2, res2 = capital_schedule(Assumptions.load(str(p)), "rotation", 20, "central")
    assert capex2.sum() == 0 and res2 == 0


# ------------------------------------------------------------------ risk
def test_fsd_detected_for_shifted_distribution():
    rng = np.random.default_rng(1)
    x = rng.normal(100, 50, 5000)
    d = dominance(x + 50, x)
    assert d["fsd"] and d["verdict"] == "FSD"
    assert dominance(x, x + 50)["verdict"] == "dominated (FSD)"


def test_ssd_for_mean_preserving_spread():
    rng = np.random.default_rng(2)
    base = rng.normal(100, 20, 20000)
    spread = rng.normal(100, 80, 20000)
    d = dominance(base, spread)
    assert not d["fsd"] and d["ssd"]


def test_barrett_donald_rejects_false_dominance():
    rng = np.random.default_rng(3)
    x, y = rng.normal(0, 1, 200), rng.normal(1, 1, 200)
    assert barrett_donald(x, y, 1, 199, rng) < 0.05   # x does not dominate y
    assert barrett_donald(y, x, 1, 199, rng) > 0.10   # y dominating x is not rejected


def test_certainty_equivalent_properties():
    x = np.array([-100.0, 100.0, 300.0])
    assert certainty_equivalent(x, 0, 5000) == pytest.approx(x.mean())
    assert certainty_equivalent(x, 2, 5000) < x.mean()
    assert certainty_equivalent(x, 4, 5000) < certainty_equivalent(x, 2, 5000)
    sf = serf({"Baseline": np.full(10, 50.0), "A": np.full(10, 80.0)}, 5000)
    assert np.allclose(sf[sf.system == "A"]["risk_premium_vs_baseline"], 30.0)


# ------------------------------------------------------------------ integration (committed GM outputs)
@pytest.mark.skipif(not REPO_FILES, reason="run from the repo root")
def test_recorded_gross_margins_reproduced_at_reference_prices():
    from src.analysis.investment.inputs import build_trial_data, plot_year_gm, reference_prices

    td = build_trial_data()
    ref = reference_prices()
    P = np.array([float(ref.get(c, 0.0)) for c in td.commodities])
    P[td.commodities.index("hay")] = float(ref["oats"])
    P[td.commodities.index("agistment")] = 0.0
    gm = plot_year_gm(td, P)
    no_hay = td.Q[:, td.commodities.index("hay")] == 0
    assert np.allclose(gm[no_hay], td.plot_years["gm_recorded"].to_numpy()[no_hay], atol=1e-6)


@pytest.mark.skipif(not REPO_FILES, reason="run from the repo root")
def test_end_to_end_small(tmp_path):
    from src.analysis.investment import run_investment_analysis

    res = run_investment_analysis(n_farm_iterations=40, n_risk_draws=500, n_bootstrap=40,
                                  n_industry_draws=200, run_sensitivity=False, output_dir=str(tmp_path))
    assert not res["farm"].empty and "bcr_mean" in res["industry"]["project"]
    for f in ("assumptions_register.csv", "farm_investment_by_zone.csv", "stochastic_dominance.csv",
              "project_summary.csv", "data_query_revenue_vs_yield.csv"):
        assert (tmp_path / f).exists()


@pytest.mark.skipif(not REPO_FILES, reason="run from the repo root")
def test_confidence_weighting_scales_benefits():
    from src.analysis.investment.industry import industry_analysis

    a = Assumptions.load()
    deltas = {("SA_MNLYE", "More pulses"): np.full(200, 60.0)}
    gate = {("SA_MNLYE", "More pulses"): 1e5}

    def pv(conf):
        out = industry_analysis(a, deltas, gate, 400, np.random.default_rng(0),
                                confidence={("SA_MNLYE", "More pulses"): conf}, evidence_weighting=True,
                                reallocate=False)
        return out["table"]["pv_industry_benefit_mean"].iloc[0]

    full, half = pv(1.0), pv(0.5)
    assert full > 0 and half == pytest.approx(full / 2, rel=0.02)


def test_profile_overlay_merges_and_validates(tmp_path):
    base = {"r": {"central": 0.05, "low": 0.03, "high": 0.07, "source": "s", "status": "verified"},
            "g": {"x": {"central": 1, "source": "s", "status": "judgement"}, "y": {"central": 2, "source": "s", "status": "judgement"}}}
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(base))
    (tmp_path / "a_conv.yaml").write_text(yaml.safe_dump({"g": {"x": {"central": 9, "source": "IA", "status": "snippet"}}}))
    a = Assumptions.load(str(tmp_path / "a.yaml"), "conv")
    assert a.get("g.x") == 9 and a.get("g.y") == 2 and a.get("r") == 0.05
    (tmp_path / "a_bad.yaml").write_text(yaml.safe_dump({"g": {"x": {"central": 9}}}))
    with pytest.raises(ValueError):
        Assumptions.load(str(tmp_path / "a.yaml"), "bad")


@pytest.mark.skipif(not REPO_FILES, reason="run from the repo root")
def test_reallocation_moves_weak_systems_area_to_better_ones():
    from src.analysis.investment.industry import industry_analysis

    a = Assumptions.load()
    z = "SA_MNLYE"
    deltas = {(z, "More pulses"): np.full(200, 60.0), (z, "Pulse-canola"): np.full(200, -40.0),
              (z, "Intercropping"): np.full(200, -60.0)}
    gate = {(z, "More pulses"): 1e5, (z, "Pulse-canola"): -1e5, (z, "Intercropping"): -1e5}
    conf = {k: (1.0 if k[1] == "More pulses" else 0.0) for k in deltas}
    kw = dict(confidence=conf, evidence_weighting=True)
    on = industry_analysis(a, deltas, gate, 400, np.random.default_rng(0), reallocate=True, **kw)["table"]
    off = industry_analysis(a, deltas, gate, 400, np.random.default_rng(0), reallocate=False, **kw)["table"]
    get = lambda t, b: t.set_index("broad_category").loc[b]
    # weaker systems get nothing; the better one takes the pooled area (rotation 8% + multicrop 2% + rotation 8%, capped)
    assert get(on, "Pulse-canola")["pv_industry_benefit_mean"] == 0
    assert get(on, "More pulses")["adoption_ceiling_share_mean"] > get(off, "More pulses")["adoption_ceiling_share_mean"] * 1.5
    assert get(on, "More pulses")["adoption_ceiling_share_mean"] <= a.get("adoption.joint_cap_share") + 1e-9
