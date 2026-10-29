import numpy as np
import pandas as pd
import pytest

import qualitylab as ql
from qualitylab import constants as K


@pytest.fixture
def sub5():
    rng = np.random.default_rng(3)
    return rng.normal(10, 1, (25, 5))


# --- variables charts --------------------------------------------------------

def test_xbar_r_matches_textbook_formulas(sub5):
    xr, rr = ql.xbar_r(sub5)
    xbb = sub5.mean(1).mean()
    rbar = (sub5.max(1) - sub5.min(1)).mean()
    assert xr.center[0] == pytest.approx(xbb)
    assert xr.ucl[0] == pytest.approx(xbb + K.A2(5) * rbar)
    assert xr.lcl[0] == pytest.approx(xbb - K.A2(5) * rbar)
    assert rr.center[0] == pytest.approx(rbar)
    assert rr.ucl[0] == pytest.approx(K.D4(5) * rbar)
    assert rr.lcl[0] == pytest.approx(K.D3(5) * rbar)


def test_xbar_s_matches_textbook_formulas(sub5):
    xs, ss = ql.xbar_s(sub5)
    xbb = sub5.mean(1).mean()
    sbar = sub5.std(1, ddof=1).mean()
    assert xs.ucl[0] == pytest.approx(xbb + K.A3(5) * sbar)
    assert ss.center[0] == pytest.approx(sbar)
    assert ss.ucl[0] == pytest.approx(K.B4(5) * sbar)
    assert ss.lcl[0] == pytest.approx(K.B3(5) * sbar)


def test_xbar_s_variable_sizes():
    rng = np.random.default_rng(0)
    rows = [rng.normal(0, 2, k) for k in rng.integers(3, 9, 40)]
    xs, ss = ql.xbar_s(rows)
    n = np.array([len(r) for r in rows])
    # wider limits for smaller subgroups
    w = xs.ucl - xs.center
    assert w[np.argmin(n)] > w[np.argmax(n)]
    assert xs.params["sigma"] == pytest.approx(2, rel=0.15)


def test_xbar_r_rejects_unequal_sizes():
    with pytest.raises(ValueError, match="xbar_s"):
        ql.xbar_r([[1, 2, 3], [1, 2]])


def test_dataframe_with_nan_padding_and_labels():
    df = pd.DataFrame({"a": [1, 2, 3, 4.0], "b": [2, 3, 4, 5.0], "c": [3, np.nan, 5, 6.0]},
                      index=list("wxyz"))
    xs, _ = ql.xbar_s(df)
    assert list(xs.labels) == list("wxyz")
    assert xs.statistic[1] == pytest.approx(2.5)


def test_imr_formulas():
    x = np.array([10.0, 12, 11, 13, 12, 14, 11, 12, 13, 12])
    i, mr = ql.imr(x)
    mrbar = np.abs(np.diff(x)).mean()
    assert i.ucl[0] == pytest.approx(x.mean() + 2.660 * mrbar, rel=1e-3)
    assert mr.ucl[0] == pytest.approx(3.267 * mrbar, rel=1e-3)
    assert mr.lcl[0] == 0
    assert np.isnan(mr.statistic[0])


def test_imr_detects_planted_outlier():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 50)
    x[30] = 6
    i, _ = ql.imr(x)
    assert 30 in i.violations[1]


def test_phase1_limits_fixed_then_monitor():
    rng = np.random.default_rng(2)
    x = np.concatenate([rng.normal(0, 1, 30), rng.normal(3, 1, 20)])
    i, _ = ql.imr(x, phase1=30)
    assert i.center[0] == pytest.approx(x[:30].mean())
    assert i.phase1.sum() == 30
    first = i.first_signal(phase2_only=True)
    assert first is not None and first >= 30


def test_exclude_and_revise():
    rng = np.random.default_rng(4)
    X = rng.normal(50, 2, (20, 4))
    X[7] += 12  # a known special cause
    xr0, _ = ql.xbar_r(X)
    assert 7 in xr0.violations[1]
    xr1, _ = ql.xbar_r(X, exclude=[7])
    assert xr1.center[0] == pytest.approx(np.delete(X, 7, 0).mean())
    xr2, _ = ql.xbar_r(X, revise=True)
    assert xr2.excluded[7]
    assert xr2.center[0] == pytest.approx(xr1.center[0])


def test_known_standards():
    x = np.zeros(10)
    i, mr = ql.imr(x + np.arange(10) * 0.01, mu=0, sigma=1)
    assert i.ucl[0] == 3 and i.lcl[0] == -3


# --- attributes charts ---------------------------------------------------------

def test_p_chart_variable_n():
    d = np.array([5, 8, 4, 10, 6])
    n = np.array([100, 150, 80, 200, 120])
    p = ql.p_chart(d, n)
    pbar = d.sum() / n.sum()
    assert p.center[0] == pytest.approx(pbar)
    assert p.ucl[2] == pytest.approx(pbar + 3 * np.sqrt(pbar * (1 - pbar) / 80))
    assert (p.lcl >= 0).all()


def test_p_chart_validation():
    with pytest.raises(ValueError):
        ql.p_chart([5, 200], [100, 100])


def test_laney_on_overdispersed_data():
    df = ql.datasets.load("online_orders")
    std = ql.p_chart(df.orders_returned, df.orders_shipped)
    lan = ql.p_chart(df.orders_returned, df.orders_shipped, laney=True)
    assert len(std.violations[1]) >= 5
    assert len(lan.violations[1]) <= 2
    assert lan.params["sigma_z"] > 2


def test_laney_factor_near_one_for_binomial_data():
    rng = np.random.default_rng(0)
    n = rng.integers(200, 400, 200)
    d = rng.binomial(n, 0.05)
    lan = ql.p_chart(d, n, laney=True)
    assert lan.params["sigma_z"] == pytest.approx(1, abs=0.15)


def test_np_c_u_charts():
    d = np.array([3, 5, 2, 4, 6, 3])
    npc = ql.np_chart(d, 50)
    pbar = d.sum() / 300
    assert npc.center[0] == pytest.approx(50 * pbar)
    assert npc.ucl[0] == pytest.approx(50 * pbar + 3 * np.sqrt(50 * pbar * (1 - pbar)))

    c = ql.c_chart([4, 6, 5, 7, 3, 20])
    assert 5 in c.violations[1]
    assert c.lcl[0] == 0  # 7.5 - 3*sqrt(7.5) < 0

    u = ql.u_chart([10, 12, 30], [2.0, 3.0, 5.0])
    ubar = 52 / 10
    assert u.center[0] == pytest.approx(ubar)
    assert u.ucl[0] == pytest.approx(ubar + 3 * np.sqrt(ubar / 2))


# --- EWMA & CUSUM --------------------------------------------------------------

def test_ewma_recursion_and_limits():
    x = np.array([1.0, -1.0, 2.0, 0.5])
    e = ql.ewma(x, lam=0.25, mu=0, sigma=1, L=3)
    z = 0
    for i, xi in enumerate(x):
        z = 0.25 * xi + 0.75 * z
        assert e.statistic[i] == pytest.approx(z)
        lim = 3 * np.sqrt(0.25 / 1.75 * (1 - 0.75 ** (2 * (i + 1))))
        assert e.ucl[i] == pytest.approx(lim)
    ea = ql.ewma(x, lam=0.25, mu=0, sigma=1, asymptotic=True)
    assert ea.ucl[0] == pytest.approx(3 * np.sqrt(0.25 / 1.75))


def test_cusum_hand_example():
    # μ0=10, σ=1, k=0.5, h=5  ->  K=0.5, H=5
    x = np.array([9.45, 7.99, 9.29, 11.66, 12.16, 10.18, 8.04, 11.46, 9.2, 10.34,
                  9.03, 11.47, 10.51, 9.4, 10.08, 9.37, 10.62, 10.31, 8.52, 10.84,
                  10.9, 9.33, 12.29, 11.5, 10.6, 11.08, 10.38, 11.62, 11.31, 10.52])
    r = ql.cusum(x, mu=10, sigma=1, k=0.5, h=5)
    cp = 0.0
    for i, xi in enumerate(x):
        cp = max(0.0, xi - 10.5 + cp)
        assert r.statistic[i] == pytest.approx(cp)
    # first signal at the 29th observation
    assert r.violations[1][0] == 28
    assert r.extra["N_plus"][28] == 7
    assert r.extra["shift_estimate"][28] == pytest.approx(10.5 + r.statistic[28] / 7)


def test_cusum_detects_downward_shift():
    rng = np.random.default_rng(5)
    x = np.concatenate([rng.normal(0, 1, 40), rng.normal(-1, 1, 40)])
    r = ql.cusum(x, mu=0, sigma=1)
    assert r.violations[1].size and r.violations[1][0] >= 40
    assert r.extra["C_minus"].min() < -5


# --- general ----------------------------------------------------------------

def test_result_frame_and_summary(sub5):
    xr, _ = ql.xbar_r(sub5)
    f = xr.to_frame()
    assert {"Xbar", "CL", "UCL", "LCL", "rules_violated", "phase"} <= set(f.columns)
    assert "Xbar chart" in xr.summary()


def test_subgroups_from_long():
    long = pd.DataFrame({"lot": ["A", "A", "A", "B", "B", "C", "C", "C"],
                         "y": [1, 2, 3, 4, 5, 6, 7, 8.0]})
    wide = ql.subgroups_from_long(long, "y", "lot")
    assert list(wide.index) == ["A", "B", "C"]
    assert np.isnan(wide.loc["B", "x3"])
    xs, _ = ql.xbar_s(wide)
    assert xs.statistic.tolist() == [2, 4.5, 7]
