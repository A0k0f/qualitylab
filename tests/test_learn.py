"""Learning Lab mission engines: every 'right answer' the app teaches must actually be right."""
import numpy as np
import pytest
from scipy import stats

from qualitylab.learn import capability_game as CG
from qualitylab.learn import concepts as C
from qualitylab.learn import funnel as F
from qualitylab.learn import manager_game as MG
from qualitylab.learn import pareto_game as PG
from qualitylab.learn import redbeads as RB
from qualitylab.learn import signals as S

# --- red beads -------------------------------------------------------------------


def test_red_bead_distribution():
    rng = np.random.default_rng(0)
    counts = np.array([list(RB.scoop(rng).values()) for _ in range(20000)]).ravel()
    assert counts.mean() == pytest.approx(10, abs=0.05)
    assert counts.std() == pytest.approx(np.sqrt(50 * 0.2 * 0.8), abs=0.05)


def test_red_bead_limits_and_regression_to_mean():
    lim = RB.control_limits([10] * 18)
    assert lim["center"] == pytest.approx(10)
    assert lim["ucl"] == pytest.approx(10 + 3 * np.sqrt(8))
    r = RB.regression_to_mean(reps=50_000)
    assert r["worst_next"] == pytest.approx(10, abs=0.05)
    assert r["best_next"] == pytest.approx(10, abs=0.05)
    assert r["worst_today"] > 13 and r["best_today"] < 7


def test_intervention_effects_and_blame():
    days = [RB.DayResult(1, {"A": 15, "B": 5}), RB.DayResult(2, {"A": 10, "B": 9})]
    acts = {1: {"A": "Warning", "B": "Praise + bonus"}}
    e = RB.intervention_effects(days, acts)
    assert e["Warning"]["mean_change"] == -5 and e["Praise + bonus"]["mean_change"] == 4
    assert RB.blame_index(acts) == 1.0
    assert RB.blame_index({1: {"A": "No action"}}) == 0.0


def test_only_supplier_changes_the_system():
    for k, opt in RB.SYSTEM_CHANGES.items():
        assert (opt["red_share"] < RB.RED_SHARE) == (k == "supplier")


# --- signal or noise ----------------------------------------------------------------


@pytest.mark.parametrize("seed", range(25))
def test_signal_rounds_have_unambiguous_ground_truth(seed):
    for phase in ("A", "B"):
        rounds = S.make_phase(phase, seed * 7 + (phase == "B"))
        assert sorted(r.category for r in rounds) == sorted(S.PHASE_MIX)
        assert len({r.context["name"] for r in rounds}) == len(rounds)
        for r in rounds:
            z = r.z
            if r.is_signal:
                assert r.rules_fired, "a signal round must be detectable by the taught rules"
                first = min(min(v) for v in r.rules_fired.values())
                assert first >= r.start
                assert (np.abs(z).max() > 3) == (r.category == "signal_obvious")
            else:
                assert not r.rules_fired
                assert np.abs(z).max() < 3
                if r.category == "noise_tempting":
                    assert 2.3 < np.abs(z).max() < 2.95


def test_dprime_and_payoff():
    d = S.dprime(2, 4, 2, 4)
    assert d["dprime"] == pytest.approx(0)
    assert S.dprime(4, 4, 0, 4)["dprime"] > 2
    h, f = 4.5 / 5, 0.5 / 5
    assert S.dprime(4, 4, 0, 4)["dprime"] == pytest.approx(stats.norm.ppf(h) - stats.norm.ppf(f))
    assert S.payoff(True, True) > 0 > S.payoff(False, True) > S.payoff(True, False)
    assert S.payoff(False, False) == 0


# --- funnel ------------------------------------------------------------------------


@pytest.mark.parametrize("rule", [1, 2, 3, 4])
def test_funnel_rules_match_theory(rule):
    rng = np.random.default_rng(rule)
    n = 60
    ms = np.mean([F.run_rule(rule, rng.normal(0, F.SIGMA, n))["sd"] ** 2 for _ in range(3000)])
    assert np.sqrt(ms) == pytest.approx(F.theoretical_sd(rule, n), rel=0.04)


def test_manual_replay_reproduces_rule_2():
    rng = np.random.default_rng(3)
    e = rng.normal(0, F.SIGMA, 16)
    adj, aim = [], F.TARGET
    for i in range(15):  # compensate each fill's error, as rule 2 does
        x = aim + e[i]
        adj.append(-(x - F.TARGET))
        aim += adj[-1]
    rep = F.replay_manual(adj, e)
    np.testing.assert_allclose(rep["fills"], F.run_rule(2, e)["fills"])
    assert F.tampering_index(adj, rep["fills"])["slope"] == pytest.approx(-1)
    assert F.tampering_index([0.0] * 15, rep["fills"])["share_adjusted"] == 0


# --- capability ------------------------------------------------------------------------


def test_capability_game_numbers():
    cp, cpk = CG.cp_cpk(CG.MEAN0, CG.SIGMA0)
    assert cp == pytest.approx(0.1 / 0.09) and cpk == pytest.approx(0.03 / 0.045)
    assert CG.ppm(CG.MEAN0, CG.SIGMA0) == pytest.approx(stats.norm.sf(2) * 1e6, rel=1e-3)
    best = CG.cheapest_solution()
    assert sorted(best["actions"]) == ["center", "tooling"] and best["cost"] == 15_000
    assert not CG.outcome(["machine"])["meets"]           # no centering → fails despite the best machine
    assert not CG.outcome(["center"])["meets"]            # centering alone → Cpk = Cp = 1.11
    inspect = CG.outcome(["inspect"])
    assert inspect["cpk"] == pytest.approx(cpk) and inspect["ppm_shipped"] < inspect["ppm_made"]
    assert CG.outcome(["relax"])["cpk"] == pytest.approx(cpk)


@pytest.mark.parametrize("seed", range(10))
def test_quadrant_series_match_their_labels(seed):
    rng = np.random.default_rng(seed)
    for k, q in CG.QUADRANTS.items():
        x = CG.quadrant_series(k, rng)
        beyond = np.abs(x - q["mean"]) > 3 * q["sigma"]
        assert (not beyond.any()) == q["in_control"]
        assert ((np.abs(x) > 3).mean() == 0) == q["capable"]


# --- Pareto / cost of quality -----------------------------------------------------------


def test_pareto_optimum_is_exact_and_beats_rules_of_thumb():
    best = PG.optimal()
    assert best["within_budget"]
    assert sorted(best["chosen"]) == ["billing", "coaching", "packaging", "scan"]
    for by in ("count", "cost", "ratio"):
        assert PG.greedy(by)["annual_saving"] < best["annual_saving"]
    t = PG.COMPLAINTS
    assert t["complaints_per_year"].idxmax() != t["annual_cost"].idxmax()


def test_coq_items_balanced():
    cats = [c for _, c in PG.COQ_ITEMS]
    assert all(cats.count(c) == 2 for c in PG.COQ_CATEGORIES)


def test_manager_menu():
    df = MG.simulate_menu(reps=120)
    assert len(df) == 32 and df.index.is_unique
    best = df.loc[df["annual_cost"].idxmin()]
    assert best["check"] == "shewhart"
    assert df.attrs["today"]["annual_cost"] > best["annual_cost"]
    assert (df["regret"] >= 0).all()


# --- concept check and survey -----------------------------------------------------------


def test_concept_items_well_formed():
    assert len(C.ITEMS) == 12 and len(C.ITEM_BY_ID) == 12
    for it in C.ITEMS:
        assert 0 <= it.answer < len(it.options) and len(set(it.options)) == len(it.options)
    sc = C.score({i.id: i.answer for i in C.ITEMS})
    assert sc["score"] == 12 and sc["pct"] == 1
    assert sorted(C.order(1)) == sorted(i.id for i in C.ITEMS)


def test_sus_and_gain():
    assert C.sus_score([3] * 10) == 50
    assert C.sus_score([5, 1] * 5) == 100
    assert C.sus_score([1, 5] * 5) == 0
    assert C.normalized_gain(0.5, 0.75) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        C.sus_score([3] * 9)
