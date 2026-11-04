"""Process Lab: results computed from student settings must agree with SPC theory."""
import math

import numpy as np
import pytest
from scipy import stats

from qualitylab.learn import process_lab as PL


def exp(**kw):
    changes = kw.pop("changes", [])
    mon = kw.pop("monitor", {})
    return PL.Experiment(PL.Process(**kw), changes, PL.Monitor(**mon))


def test_validation_messages():
    assert exp().problems() == []
    assert exp(lsl=5, usl=4).problems()
    assert exp(sigma=0).problems()
    assert exp(lsl=None, usl=None).problems()
    assert exp(baseline=58).problems()
    assert exp(changes=[PL.Change("spread", 30, -1)]).problems()
    with pytest.raises(ValueError):
        PL.run(exp(sigma=-1), 1)


def test_in_control_false_alarm_rate_matches_three_sigma_theory():
    # known limits, rule 1 only, X̄ chart alone: P(signal) = 2 Φ(−3) per sample
    e = exp(samples=500, baseline=10, n=5, monitor=dict(limits_from="known", rules="limits"))
    rate = []
    for s in range(60):
        r = PL.run(e, s)
        main = r["main"]
        mon = np.arange(e.process.samples) >= e.process.baseline
        rate.append(np.isin(np.flatnonzero(mon), main.out_of_control).mean())
    assert np.mean(rate) == pytest.approx(2 * stats.norm.sf(3), rel=0.15)


def test_detection_delay_matches_arl_for_a_shift():
    e = exp(samples=400, baseline=20, n=5, changes=[PL.Change("shift", 21, 0.5)],
            monitor=dict(limits_from="known", rules="limits", react=False))
    p_xbar = 1 / PL.theoretical_shewhart(e)["shifts"][0]["arl1"]     # δ√n = 1.118 → ARL ≈ 33.4
    # the R chart (unaffected by the shift) also signals with P(R > UCL_R); estimate it once
    from qualitylab import constants as K
    z = np.random.default_rng(0).standard_normal((400_000, 5))
    p_r = ((z.max(1) - z.min(1)) > K.d2(5) + 3 * K.d3(5)).mean()
    theory = 1 / (p_xbar + p_r - p_xbar * p_r)
    rep = PL.replicate(e, reps=600, seed=3)
    assert rep["changes"][0]["detected"] > 0.99
    assert rep["changes"][0]["delay_mean"] == pytest.approx(theory, rel=0.08)


def test_bigger_shifts_are_caught_sooner_and_ewma_beats_shewhart_on_small_shifts():
    def delay(size, chart):
        e = exp(samples=300, n=1, changes=[PL.Change("shift", 21, size)],
                monitor=dict(chart=chart, rules="limits", limits_from="known", react=False))
        return PL.replicate(e, reps=300, seed=5)["changes"][0]["delay_mean"]
    assert delay(2.0, "shewhart") < delay(1.0, "shewhart") < delay(0.5, "shewhart")
    # published ARLs at a 0.5σ shift: Shewhart ≈ 155, EWMA(0.2, 2.962) ≈ 52, CUSUM(0.5, 5) ≈ 38; the Shewhart
    # figure here is lower because runs are cut off after 280 samples and the MR chart also signals
    assert delay(0.5, "ewma") < 0.7 * delay(0.5, "shewhart")
    assert delay(0.5, "cusum") < 0.7 * delay(0.5, "shewhart")


def test_reacting_removes_the_problem_and_cuts_defects():
    base = dict(samples=120, changes=[PL.Change("shift", 40, 2.0)])
    react = PL.replicate(exp(**base, monitor=dict(react=True)), reps=100, seed=1)
    ignore = PL.replicate(exp(**base, monitor=dict(react=False)), reps=100, seed=1)
    assert react["oos_share"] < 0.5 * ignore["oos_share"]
    r = PL.run(exp(**base, monitor=dict(react=True)), 7)
    fix = r["changes"][0]["fixed_at"]
    assert fix is not None and np.allclose(r["mu"][fix:], 100.0)   # back on target after the fix


def test_out_of_spec_and_costs_add_up():
    e = exp(mean=101.0, sigma=1.0, lsl=97, usl=103, samples=50, units_per_sample=1000,
            monitor=dict(react=False))
    r = PL.run(e, 2)
    p = stats.norm.cdf(97, 101, 1) + stats.norm.sf(103, 101, 1)
    assert r["oos_share"] == pytest.approx(p)
    c = r["costs"]
    assert c["checking"] == pytest.approx(2.0 * 5 * 50)
    assert c["defects"] == pytest.approx(25.0 * p * 1000 * 50)
    assert c["investigations"] == 0 and c["total"] == pytest.approx(c["checking"] + c["defects"])
    assert r["capability"]["true_cpk"] == pytest.approx(2 / 3)


def test_spread_increase_is_caught_by_the_range_chart():
    e = exp(samples=200, changes=[PL.Change("spread", 30, 2.5)], monitor=dict(react=False, rules="limits"))
    rep = PL.replicate(e, reps=100, seed=2)
    assert rep["changes"][0]["detected"] > 0.95 and rep["changes"][0]["delay_median"] <= 3


def test_change_inside_the_baseline_contaminates_the_limits():
    clean = exp(samples=80, changes=[PL.Change("shift", 41, 1.0)], monitor=dict(react=False))
    dirty = exp(samples=80, changes=[PL.Change("shift", 11, 1.0)], monitor=dict(react=False))
    a, b = PL.run(clean, 4), PL.run(dirty, 4)
    assert b["changes"][0]["in_baseline"] and not a["changes"][0]["in_baseline"]
    assert b["main"].ucl[0] > a["main"].ucl[0]  # limits widened by the shift hidden in the baseline


def test_runs_are_reproducible_and_seeded():
    e = exp(changes=[PL.Change("drift", 30, 0.05)])
    a, b, c = PL.run(e, 11), PL.run(e, 11), PL.run(e, 12)
    assert np.array_equal(a["X"], b["X"]) and not np.array_equal(a["X"], c["X"])


def test_diff_names_changed_settings():
    a = exp().to_dict()
    b = exp(n=3, monitor=dict(chart="ewma")).to_dict()
    assert PL.diff(a, b) == ["process.n", "monitor.chart"]
    assert PL.diff(None, b) == []
    assert PL.Experiment.from_dict(b).to_dict() == b


def test_every_chart_and_sample_size_runs():
    for n in (1, 2, 5, 10, 12, 25):
        for chart in PL.CHART_TYPES:
            for rules in PL.RULE_SETS:
                r = PL.run(exp(n=n, changes=[PL.Change("shift", 35, 1.5)],
                               monitor=dict(chart=chart, rules=rules)), n)
                assert r["chart_name"] and math.isfinite(r["costs"]["total"])
