import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

import qualitylab as ql  # noqa: E402
from qualitylab import arl  # noqa: E402

# --- capability -----------------------------------------------------------------


def test_capability_recovers_true_indices():
    rng = np.random.default_rng(0)
    X = rng.normal(25.01, 0.012, (200, 4))
    cap = ql.capability(X, 24.95, 25.05)
    assert cap.sigma_method == "Rbar/d2"
    assert cap.indices["Cp"] == pytest.approx(0.10 / 0.072, rel=0.05)
    assert cap.indices["Cpk"] == pytest.approx(0.04 / 0.036, rel=0.06)
    lo, hi = cap.intervals["Cp"]
    assert lo < cap.indices["Cp"] < hi
    assert cap.indices["Cpk"] == min(cap.indices["Cpu"], cap.indices["Cpl"])
    assert cap.target == pytest.approx(25.0)


def test_capability_individuals_one_sided():
    rng = np.random.default_rng(1)
    x = rng.normal(4, 0.5, 300)
    cap = ql.capability(x, usl=6)
    assert "Cp" not in cap.indices and "Cpu" in cap.indices
    assert cap.indices["Cpk"] == cap.indices["Cpu"]
    assert cap.ppm.loc["expected (overall)", "below_LSL"] == 0
    assert cap.sigma_method == "MRbar/d2"


def test_capability_ppm_matches_normal_tail():
    from scipy import stats

    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 5000)
    cap = ql.capability(x, -3, 3)
    m, s = cap.mean, cap.sigma_overall
    expected = (stats.norm.cdf((-3 - m) / s) + stats.norm.sf((3 - m) / s)) * 1e6
    assert cap.ppm.loc["expected (overall)", "total"] == pytest.approx(expected)


def test_capability_interpretation_flags_off_center_and_instability():
    rng = np.random.default_rng(3)
    X = rng.normal(0, 1, (30, 5)) + np.repeat(rng.normal(0, 1.2, 30)[:, None], 5, 1) + 1.5
    cap = ql.capability(X, -6, 6)
    text = cap.interpretation()
    assert "off-center" in text
    assert "Ppk" in text


def test_capability_errors():
    with pytest.raises(ValueError):
        ql.capability(np.arange(10.0))
    with pytest.raises(ValueError):
        ql.capability(np.arange(10.0), 5, 1)


# --- Hotelling T² ------------------------------------------------------------------


def test_t2_limits_and_bottling_example():
    df = ql.datasets.load("bottling_line")
    key = ql.datasets.answer_key("bottling_line")
    t2 = ql.hotelling_t2(df)
    odd = key["unusual_bottle"] - 1
    assert odd in t2.violations[1]
    # ...while none of the three univariate I charts flags that bottle
    for col in df.columns:
        i, _ = ql.imr(df[col])
        assert odd not in i.violations[1]


def test_t2_phase2_uses_f_limit():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3))
    r = ql.hotelling_t2(X, phase1=40)
    assert r.ucl[0] != r.ucl[-1]
    assert r.phase1.sum() == 40
    assert r.extra["contributions"].shape == (60, 3)


def test_t2_false_alarm_rate():
    rng = np.random.default_rng(1)
    hits = 0
    for _ in range(200):
        r = ql.hotelling_t2(rng.normal(size=(50, 4)), alpha=0.01)
        hits += r.violations[1].size
    assert hits / (200 * 50) == pytest.approx(0.01, abs=0.004)


# --- Pareto ---------------------------------------------------------------------


def test_pareto_from_raw_labels():
    t = ql.pareto(["a"] * 50 + ["b"] * 30 + ["c"] * 15 + ["d"] * 5)
    assert t.index.tolist() == ["a", "b", "c", "d"]
    assert t["cumulative_share"].iloc[-1] == pytest.approx(1)
    assert t["vital_few"].tolist() == [True, True, False, False]


def test_pareto_from_dataframe_counts_and_other():
    df = pd.DataFrame({"cause": list("abcdef"), "n": [40, 30, 10, 3, 2, 1]})
    t = ql.pareto(df, category="cause", count="n", other_below=0.05)
    assert t.index[-1] == "Other" and t.loc["Other", "count"] == 6


# --- datasets -------------------------------------------------------------------


@pytest.mark.parametrize("name", ql.datasets.available())
def test_datasets_load_and_are_reproducible(name):
    a = ql.datasets.load(name)
    b = ql.datasets.load(name)
    pd.testing.assert_frame_equal(a, b)
    c = ql.datasets.load(name, seed="student-01234")
    assert not a.equals(c)
    assert isinstance(ql.datasets.answer_key(name), dict)


def test_similar_codes_give_different_data():
    a = ql.datasets.load("shaft_diameter", "S0051")
    b = ql.datasets.load("shaft_diameter", "S0052")
    assert not a.equals(b)
    pd.testing.assert_frame_equal(ql.datasets.load("shaft_diameter", " s0051 "), a)


def test_default_datasets_show_their_planted_causes():
    df = ql.datasets.load("invoice_errors")
    key = ql.datasets.answer_key("invoice_errors")
    p = ql.p_chart(df.invoices_with_errors, df.invoices_audited, labels=df.index)
    assert key["problem_week"] - 1 in p.out_of_control

    df = ql.datasets.load("pcb_defects")
    key = ql.datasets.answer_key("pcb_defects")
    assert key["bad_board"] - 1 in ql.c_chart(df.defects).violations[1]

    df = ql.datasets.load("coffee_fill")
    key = ql.datasets.answer_key("coffee_fill")
    for seed in (None, 1, 2, 3, "student-42"):
        df = ql.datasets.load("coffee_fill", seed)
        key = ql.datasets.answer_key("coffee_fill", seed)
        xr, rr = ql.xbar_r(df.filter(like="bottle"), phase1=15, revise=True)
        # the loose-nozzle subgroup is caught on the R chart and dropped from the limits
        assert key["high_spread_sample"] - 1 in rr.violations[1]
        assert xr.excluded[key["high_spread_sample"] - 1]
        # the mean shift is detected in Phase II, after it starts
        first = xr.first_signal(phase2_only=True)
        assert first is not None and first >= key["mean_shift_starts_at_sample"] - 1


# --- ARL ------------------------------------------------------------------------


def test_shewhart_arl_exact():
    assert arl.shewhart_arl(0) == pytest.approx(370.4, abs=0.1)
    assert arl.shewhart_arl(1) == pytest.approx(43.9, abs=0.1)


@pytest.mark.slow
def test_ewma_and_cusum_arl_match_literature():
    # Lucas & Saccucci (1990): λ=0.2, L=2.962 -> ARL0 ≈ 500, ARL(1σ) ≈ 10.2
    e0 = arl.run_lengths("ewma", 0.0, reps=4000, lam=0.2, L=2.962, seed=1).mean()
    e1 = arl.run_lengths("ewma", 1.0, reps=4000, lam=0.2, L=2.962, seed=1).mean()
    assert e0 == pytest.approx(500, rel=0.08)
    assert e1 == pytest.approx(10.2, rel=0.06)
    # Two-sided tabular CUSUM, k=0.5: h=5 -> ARL0 ≈ 465, ARL(1σ) ≈ 10.4; h=4 -> 168 / 8.38
    c0 = arl.run_lengths("cusum", 0.0, reps=4000, k=0.5, h=5, seed=2).mean()
    c1 = arl.run_lengths("cusum", 1.0, reps=4000, k=0.5, h=5, seed=2).mean()
    c4 = arl.run_lengths("cusum", 0.0, reps=4000, k=0.5, h=4, seed=3).mean()
    assert c0 == pytest.approx(465, rel=0.08)
    assert c1 == pytest.approx(10.4, rel=0.06)
    assert c4 == pytest.approx(168, rel=0.08)


@pytest.mark.slow
def test_western_electric_rules_raise_false_alarms():
    # Champ & Woodall (1987): Shewhart + WE rules 1,2(8),5,6 has ARL0 ≈ 91.75
    r = arl.run_lengths("shewhart", 0.0, reps=1500, rules="western_electric", run_length=8,
                        max_len=3000, seed=4).mean()
    assert r == pytest.approx(91.75, rel=0.1)


# --- plotting smoke tests ----------------------------------------------------------


def test_plots_render():
    import matplotlib.pyplot as plt

    df = ql.datasets.load("coffee_fill")
    xr, rr = ql.xbar_r(df.filter(like="bottle"), phase1=20)
    ql.plotting.plot_pair(xr, rr)
    ql.cusum(np.random.default_rng(0).normal(size=50)).plot()
    ql.ewma(np.random.default_rng(0).normal(size=50)).plot()
    ql.capability(df.filter(like="bottle"), 11.88, 12.12).plot()
    ql.plotting.plot_pareto(ql.pareto(ql.datasets.load("complaint_reasons").complaint_reason))
    ql.hotelling_t2(ql.datasets.load("bottling_line")).plot()
    plt.close("all")
