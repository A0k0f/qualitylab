"""The what-if simulator must agree with theory wherever theory has an answer."""
import json

import numpy as np
import pytest
from scipy import stats

from qualitylab import decide
from qualitylab.scenarios import templates
from qualitylab.simulate import Costs, FailureMode, Policy, Process, _lot_accept_prob, evaluate, trace


def meas_process(**kw):
    base = dict(name="t", kind="measurement", units_per_hour=100, hours_per_day=20, days_per_year=250,
                costs=Costs(escape=1.0), target=0.0, mean=0.0, sigma=1.0, lsl=-3.0, usl=3.0)
    base.update(kw)
    return Process(**base)


def test_no_problems_no_checks_matches_closed_form():
    ev = evaluate(meas_process(), Policy("none"), reps=5)[0]
    expected = 100 * 20 * 250 * 2 * stats.norm.sf(3)
    assert ev.metrics["defects_made_per_year"].mean() == pytest.approx(expected, rel=1e-9)
    assert ev.mean_cost == pytest.approx(expected, rel=1e-9)


def test_shewhart_false_alarm_rate():
    ev = evaluate(meas_process(), Policy("shewhart", n=1, every_hours=1), reps=200)[0]
    per_check = ev.metrics["false_alarms_per_week"].mean() / (5 * 20)
    assert per_check == pytest.approx(2 * stats.norm.sf(3), rel=0.08)


def test_detection_delay_matches_arl():
    # a 1σ step shift, checked hourly with n=1 and 3σ limits: delay ≈ h·(ARL1 − ½)
    pr = meas_process(failure_modes=[FailureMode("s", every_hours=400, shift=1.0)])
    ev = evaluate(pr, Policy("shewhart", n=1, every_hours=1), reps=500)[0]
    arl1 = 1 / (stats.norm.sf(2) + stats.norm.cdf(-4))
    assert ev.metrics["hours_to_fix"].mean() == pytest.approx(arl1 - 0.5, rel=0.06)


def test_tampering_inflates_variance_like_demings_funnel():
    # re-aiming after every single-unit check: offset ~ N(0, σ²) → effective σ√2
    ev = evaluate(meas_process(), Policy("adjust", n=1, every_hours=1), reps=200)[0]
    expected = 100 * 20 * 250 * 2 * stats.norm.sf(3 / np.sqrt(2))
    assert ev.metrics["defects_made_per_year"].mean() == pytest.approx(expected, rel=0.03)


def test_external_notice_caps_problem_duration():
    pr = meas_process(failure_modes=[FailureMode("s", every_hours=200, shift=2.0)], notice_after_hours=10)
    ev = evaluate(pr, Policy("none"), reps=100)[0]
    assert ev.metrics["hours_to_fix"].mean() == pytest.approx(10, abs=1e-9)
    # time with a problem ≈ 10 / (200 + 10)
    assert ev.metrics["share_time_with_problem"].mean() == pytest.approx(10 / 210, rel=0.1)


def test_lot_oc_curve_matches_binomial():
    f = np.array([0.0, 0.01, 0.05, 0.1, 0.3])
    np.testing.assert_allclose(_lot_accept_prob(f, 50, 1), stats.binom.cdf(1, 50, f))
    np.testing.assert_allclose(_lot_accept_prob(f, 125, 3), stats.binom.cdf(3, 125, f))


def test_screening_removes_share_of_defects():
    pr = meas_process(inspection_effectiveness=0.8, costs=Costs(escape=1, per_unit_screened=0.01))
    a, b = evaluate(pr, [Policy("none"), Policy("none", final="screen")], reps=5)
    assert b.metrics["escapes_per_year"].mean() == pytest.approx(0.2 * a.metrics["escapes_per_year"].mean())
    assert b.parts["100% inspection"].mean() == pytest.approx(0.01 * pr.units_per_year)


def test_pass_fail_baseline_and_detection():
    pr = Process("pf", "pass_fail", units_per_hour=200, hours_per_day=8, days_per_year=250, defect_rate=0.01,
                 failure_modes=[FailureMode("x", every_hours=100, rate_factor=5)], notice_after_hours=40,
                 costs=Costs(escape=10, per_unit_tested=0.1))
    none, chart = evaluate(pr, [Policy("none"), Policy("shewhart", n=200, every_hours=1)], reps=200)
    assert none.metrics["hours_to_fix"].mean() == pytest.approx(40)
    assert chart.metrics["hours_to_fix"].mean() < 5
    assert chart.metrics["escapes_ppm"].mean() < none.metrics["escapes_ppm"].mean()


def test_giveaway_formula():
    from qualitylab.simulate import _giveaway

    rng = np.random.default_rng(0)
    x = rng.normal(12.1, 0.05, 2_000_000)
    assert float(_giveaway(np.float64(12.1), 0.05, 12.0)) == pytest.approx(np.maximum(x - 12.0, 0).mean(), rel=1e-3)


def test_process_json_roundtrip():
    t = templates()["filling"]
    p2 = Process.from_json(t.process.to_json())
    assert p2 == t.process
    json.dumps(p2.to_dict())


def test_validation_errors():
    with pytest.raises(ValueError):
        meas_process(sigma=0).validate()
    with pytest.raises(ValueError):
        Process("x", "pass_fail", units_per_hour=1, defect_rate=1.5).validate()
    with pytest.raises(ValueError):
        Policy("bogus")
    with pytest.raises(ValueError):
        Policy("none", final="lots", lot_n=5, lot_c=5)
    pf = Process("pf", "pass_fail", units_per_hour=10, defect_rate=0.01)
    with pytest.raises(ValueError):
        evaluate(pf, Policy("adjust", n=1, every_hours=1), reps=2)


def test_trace_shapes():
    t = templates()["cnc"]
    tr = trace(t.process, t.current, hours=40, seed=1)
    assert len(tr["t"]) == len(tr["level"]) == len(tr["active"])
    assert tr["t"][-1] == pytest.approx(40, abs=0.5)


# --- decisions -----------------------------------------------------------------

@pytest.fixture(scope="module")
def filling_decision():
    t = templates()["filling"]
    return decide.optimize(t.process, t.current, max_false_alarms_per_week=3, reps=200)


def test_optimizer_never_worse_than_today(filling_decision):
    d = filling_decision
    assert d.best.mean_cost <= d.current.mean_cost + 1e-6
    assert d.simplest.mean_cost <= d.best.mean_cost * 1.05 + 1e-6
    assert d.table["meets_constraints"].any()
    rec = d.simplest.summary()
    assert rec["false_alarms_per_week"] <= 3


def test_constraints_are_respected():
    t = templates()["filling"]
    d = decide.optimize(t.process, t.current, max_escape_ppm=500, reps=150)
    assert d.best.summary()["escapes_ppm"] <= 500
    assert d.simplest.summary()["escapes_ppm"] <= 500


def test_explain_mentions_saving(filling_decision):
    text = " ".join(decide.explain(filling_decision))
    assert "Recommended" in text and "saving" in text


def test_sensitivity_and_investments(filling_decision):
    s = decide.sensitivity(filling_decision, reps=80)
    assert set(decide.SENSITIVITY_FACTORS) == set(s["input"])
    inv = decide.compare_investments(filling_decision,
                                     [decide.Investment("free halving of variation", 0, variation_factor=0.5)],
                                     reps=80)
    assert inv.loc[1, "net_benefit"] > 0  # a free improvement must help


def test_best_aim_balances_giveaway_and_defects():
    t = templates()["filling"]
    a = decide.aim_recommendation(t.process)
    assert t.process.lsl < a["best_aim"] < t.process.mean
    assert a["annual_savings"] > 0
    # brute-force check of the optimum on a fine grid
    tab = a["table"]
    assert a["annual_cost_best"] == pytest.approx(tab["annual_cost"].min())


def test_calibrate_recovers_inputs():
    rng = np.random.default_rng(0)
    est = decide.calibrate(rng.normal(5, 0.2, 400))
    assert est["mean"] == pytest.approx(5, abs=0.05) and est["sigma"] == pytest.approx(0.2, rel=0.1)
    n = np.full(60, 500)
    est = decide.calibrate(defectives=rng.binomial(n, 0.03), sizes=n, hours_between=8)
    assert est["defect_rate"] == pytest.approx(0.03, rel=0.1)


def test_brief_renders(filling_decision):
    from qualitylab.report import build_brief

    html = build_brief(filling_decision, title="Test")
    assert html.startswith("<!doctype html>") and "Recommended" in html


@pytest.mark.parametrize("key", list(templates()))
def test_every_template_runs(key):
    t = templates()[key]
    d = decide.optimize(t.process, t.current, max_escape_ppm=t.max_escape_ppm,
                        max_false_alarms_per_week=t.max_false_alarms_per_week, reps=60, years=0.1)
    assert np.isfinite(d.simplest.mean_cost)
