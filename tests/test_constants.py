"""Constants must match the published tables (Montgomery, Appendix VI) to printed precision."""
import pytest

from qualitylab import constants as K

# n: (A2, A3, c4, B3, B4, d2, d3, D3, D4)
PUBLISHED = {
    2: (1.880, 2.659, 0.7979, 0.000, 3.267, 1.128, 0.853, 0.000, 3.267),
    3: (1.023, 1.954, 0.8862, 0.000, 2.568, 1.693, 0.888, 0.000, 2.574),
    4: (0.729, 1.628, 0.9213, 0.000, 2.266, 2.059, 0.880, 0.000, 2.282),
    5: (0.577, 1.427, 0.9400, 0.000, 2.089, 2.326, 0.864, 0.000, 2.114),
    6: (0.483, 1.287, 0.9515, 0.030, 1.970, 2.534, 0.848, 0.000, 2.004),
    7: (0.419, 1.182, 0.9594, 0.118, 1.882, 2.704, 0.833, 0.076, 1.924),
    8: (0.373, 1.099, 0.9650, 0.185, 1.815, 2.847, 0.820, 0.136, 1.864),
    10: (0.308, 0.975, 0.9727, 0.284, 1.716, 3.078, 0.797, 0.223, 1.777),
    15: (0.223, 0.789, 0.9823, 0.428, 1.572, 3.472, 0.756, 0.347, 1.653),
    20: (0.180, 0.680, 0.9869, 0.510, 1.490, 3.735, 0.729, 0.415, 1.585),
    25: (0.153, 0.606, 0.9896, 0.565, 1.435, 3.931, 0.708, 0.459, 1.541),
}


@pytest.mark.parametrize("n", sorted(PUBLISHED))
def test_published_table(n):
    a2, a3, c4, b3, b4, d2, d3, D3, D4 = PUBLISHED[n]
    assert K.A2(n) == pytest.approx(a2, abs=6e-4)
    assert K.A3(n) == pytest.approx(a3, abs=6e-4)
    assert K.c4(n) == pytest.approx(c4, abs=6e-5)
    assert K.B3(n) == pytest.approx(b3, abs=6e-4)
    assert K.B4(n) == pytest.approx(b4, abs=6e-4)
    assert K.d2(n) == pytest.approx(d2, abs=6e-4)
    assert K.d3(n) == pytest.approx(d3, abs=6e-4)
    assert K.D3(n) == pytest.approx(D3, abs=6e-4)
    assert K.D4(n) == pytest.approx(D4, abs=6e-4)


def test_E2():
    assert K.E2() == pytest.approx(2.660, abs=2e-3)  # 3/1.128 = 2.6596; table rounds


def test_d2_monte_carlo():
    import numpy as np

    rng = np.random.default_rng(1)
    x = rng.standard_normal((400_000, 7))
    r = x.max(1) - x.min(1)
    assert r.mean() == pytest.approx(K.d2(7), abs=0.005)
    assert r.std() == pytest.approx(K.d3(7), abs=0.005)


def test_bad_n():
    with pytest.raises(ValueError):
        K.d2(1)
    with pytest.raises(ValueError):
        K.c4(2.5)
    with pytest.raises(ValueError):
        K.d2(K.N_MAX + 1)


def test_table_frame():
    t = K.table(10)
    assert list(t.index) == list(range(2, 11))
    assert {"A2", "D4", "c4"} <= set(t.columns)
