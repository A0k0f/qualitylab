import numpy as np
import pytest

from qualitylab.rules import evaluate


def ev(z, rules, **kw):
    return evaluate(np.asarray(z, float), 0.0, 1.0, rules=rules, **kw)


def test_rule1_beyond_limits():
    z = [0, 0.5, 3.2, -0.1, -3.01, 2.99]
    assert ev(z, [1])[1].tolist() == [2, 4]


def test_rule2_run_of_nine():
    z = [0.2] * 8 + [-0.1] + [0.3] * 9
    assert ev(z, [2])[2].tolist() == [17]
    assert ev(z, [2], run_length=8)[2].tolist() == [7, 16, 17]


def test_rule2_zero_breaks_run():
    z = [0.1] * 5 + [0.0] + [0.1] * 5
    assert ev(z, [2])[2].size == 0


def test_rule3_trend_of_six():
    z = [0, -1, -0.5, 0, 0.5, 1, 1.5, 1.4]
    # points 1..6 strictly increase (6 points) -> flagged at position 6
    assert ev(z, [3])[3].tolist() == [6]
    assert ev([0, 1, 2, 3, 4, 3], [3])[3].size == 0  # only 5 increasing points


def test_rule4_alternating_fourteen():
    z = [(-1) ** i * 0.5 for i in range(14)]
    assert ev(z, [4])[4].tolist() == [13]
    assert ev(z[:13], [4])[4].size == 0


def test_rule5_two_of_three_beyond_2sigma():
    z = [0, 2.5, 0.1, 2.2, 0, -2.1, 0.0, -2.4]
    # window 1..3 has two points above +2σ; window 5..7 has two below −2σ
    assert ev(z, [5])[5].tolist() == [3, 7]
    # opposite sides do not count together
    assert ev([0, 2.5, -2.5, 0], [5])[5].size == 0
    # the completing point must itself be beyond 2σ
    assert ev([2.5, 2.5, 0.1], [5])[5].tolist() == [1]


def test_rule6_four_of_five_beyond_1sigma():
    z = [0, 1.2, 1.5, 0.3, 1.1, 1.3]
    assert ev(z, [6])[6].tolist() == [5]


def test_rule7_stratification():
    z = [0.1, -0.2] * 7 + [0.3]
    assert ev(z, [7])[7].tolist() == [14]


def test_rule8_mixture():
    z = [1.5, -1.6] * 4
    assert ev(z, [8])[8].tolist() == [7]


def test_nan_breaks_runs():
    z = [0.5] * 5 + [np.nan] + [0.5] * 5
    assert ev(z, [2])[2].size == 0


def test_in_control_noise_rarely_signals_rule1():
    rng = np.random.default_rng(0)
    z = rng.standard_normal(100_000)
    rate = ev(z, [1])[1].size / z.size
    assert rate == pytest.approx(0.0027, abs=0.0005)


def test_presets_and_errors():
    assert set(evaluate([0, 1], 0, 1, rules="western_electric")) == {1, 2, 5, 6}
    with pytest.raises(ValueError):
        evaluate([0, 1], 0, 1, rules="nope")
    with pytest.raises(ValueError):
        evaluate([0, 1], 0, 1, rules=[9])
