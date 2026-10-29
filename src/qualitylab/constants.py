"""Control chart constants.

Everything is derived from three primitives:

* ``d2(n)``  — E[R]/σ for the range of n normal observations
* ``d3(n)``  — SD[R]/σ for the same range
* ``c4(n)``  — E[S]/σ for the sample standard deviation (closed form)

``d2``/``d3`` come from a table produced by exact numerical integration
(``scripts/generate_constants.py``), so they agree with the published tables
(e.g. Montgomery, *Introduction to Statistical Quality Control*, Appendix VI)
to the printed precision. The familiar "textbook" factors (A2, D3, D4, A3, B3,
B4, E2) are computed from these, for any sigma multiplier L (default 3).
"""
from __future__ import annotations

from math import exp, lgamma, sqrt

from ._constants_table import D2_D3

N_MAX = max(D2_D3)


def _check_n(n: int, lo: int = 2) -> int:
    if int(n) != n or n < lo:
        raise ValueError(f"subgroup size must be an integer >= {lo}, got {n!r}")
    return int(n)


def d2(n: int) -> float:
    """Expected range of n standard normal observations."""
    n = _check_n(n)
    if n > N_MAX:
        raise ValueError(f"d2 tabulated for n <= {N_MAX}; use an S chart for larger subgroups")
    return D2_D3[n][0]


def d3(n: int) -> float:
    """Standard deviation of the range of n standard normal observations."""
    n = _check_n(n)
    if n > N_MAX:
        raise ValueError(f"d3 tabulated for n <= {N_MAX}; use an S chart for larger subgroups")
    return D2_D3[n][1]


def c4(n: int) -> float:
    """E[S]/σ for a sample of size n: sqrt(2/(n-1)) Γ(n/2)/Γ((n-1)/2)."""
    n = _check_n(n)
    return sqrt(2.0 / (n - 1)) * exp(lgamma(n / 2.0) - lgamma((n - 1) / 2.0))


# --- Textbook factors (L = 3 gives the published tables) -------------------

def A2(n: int, L: float = 3.0) -> float:
    return L / (d2(n) * sqrt(n))


def D3(n: int, L: float = 3.0) -> float:
    return max(0.0, 1.0 - L * d3(n) / d2(n))


def D4(n: int, L: float = 3.0) -> float:
    return 1.0 + L * d3(n) / d2(n)


def A3(n: int, L: float = 3.0) -> float:
    return L / (c4(n) * sqrt(n))


def B3(n: int, L: float = 3.0) -> float:
    c = c4(n)
    return max(0.0, 1.0 - L * sqrt(1.0 - c * c) / c)


def B4(n: int, L: float = 3.0) -> float:
    c = c4(n)
    return 1.0 + L * sqrt(1.0 - c * c) / c


def E2(n: int = 2, L: float = 3.0) -> float:
    """Individuals-chart factor using moving ranges of span n (2.66 for n=2)."""
    return L / d2(n)


def table(n_max: int = 25, L: float = 3.0):
    """Return the classic constants table as a pandas DataFrame."""
    import pandas as pd

    rows = []
    for n in range(2, n_max + 1):
        rows.append(
            dict(n=n, A2=A2(n, L), A3=A3(n, L), c4=c4(n), B3=B3(n, L), B4=B4(n, L),
                 d2=d2(n), d3=d3(n), D3=D3(n, L), D4=D4(n, L))
        )
    return pd.DataFrame(rows).set_index("n")
