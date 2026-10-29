"""Univariate control charts.

Variables charts : :func:`xbar_r`, :func:`xbar_s`, :func:`imr`
Attributes charts: :func:`p_chart`, :func:`np_chart`, :func:`c_chart`, :func:`u_chart`
Time-weighted    : :func:`ewma`, :func:`cusum`

Every function follows the same conventions:

``phase1``
    Which points are used to *estimate* the limits. ``None`` (default) uses
    all points — a retrospective, Phase I study. An integer ``k`` uses the
    first ``k`` points and then monitors the rest against those fixed limits
    (Phase II). A boolean mask is also accepted.
``exclude``
    Positions to leave out of the estimate (e.g. points with a known,
    removed special cause). They are still plotted.
``revise``
    If True, repeatedly drop Phase I points beyond the limits and
    re-estimate until none remain (the textbook "revised limits" procedure).
    Only do this when the causes of those points have been found and fixed.
``mu`` / ``sigma`` (or ``p``, ``c``, ``u``)
    Known/standard values. When given they are used instead of estimates.
``L``
    Sigma multiplier for the limits (3 by default).
``rules``
    Which run rules to test; see :mod:`qualitylab.rules`.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from . import constants as K
from .result import ChartResult
from .rules import evaluate

__all__ = [
    "xbar_r", "xbar_s", "imr", "p_chart", "np_chart", "c_chart", "u_chart",
    "ewma", "cusum", "subgroups_from_long",
]


# ---------------------------------------------------------------------------
# input helpers
# ---------------------------------------------------------------------------

def _labels(obj, m: int, labels) -> pd.Index:
    if labels is not None:
        idx = pd.Index(list(labels))
    elif isinstance(obj, (pd.DataFrame, pd.Series)):
        idx = obj.index
    else:
        idx = pd.RangeIndex(1, m + 1, name="sample")
    if len(idx) != m:
        raise ValueError(f"got {len(idx)} labels for {m} points")
    return idx


def _subgroups(data) -> list[np.ndarray]:
    """Rows = subgroups. Accepts 2-D array/DataFrame (NaN = missing) or list of lists."""
    if isinstance(data, pd.DataFrame):
        data = data.select_dtypes("number").to_numpy(dtype=float)
    if isinstance(data, np.ndarray) and data.ndim == 2:
        rows = [r[np.isfinite(r)] for r in data.astype(float)]
    else:
        rows = [np.asarray(r, float) for r in data]
        rows = [r[np.isfinite(r)] for r in rows]
    if len(rows) < 2:
        raise ValueError("need at least 2 subgroups")
    return rows


def subgroups_from_long(df: pd.DataFrame, value: str, subgroup: str) -> pd.DataFrame:
    """Convert long data (one measurement per row + a subgroup ID column) to wide.

    Returns a DataFrame indexed by subgroup with columns x1..xn (NaN-padded).
    """
    g = df[[subgroup, value]].dropna(subset=[value]).copy()
    g["_k"] = g.groupby(subgroup, sort=False).cumcount() + 1
    wide = g.pivot(index=subgroup, columns="_k", values=value)
    wide = wide.loc[g[subgroup].drop_duplicates()]  # keep original order
    wide.columns = [f"x{c}" for c in wide.columns]
    return wide


def _phase_mask(phase1, m: int) -> np.ndarray:
    if phase1 is None:
        return np.ones(m, bool)
    if isinstance(phase1, (int, np.integer)):
        k = int(phase1)
        if not 2 <= k <= m:
            raise ValueError(f"phase1 must be between 2 and {m}")
        mask = np.zeros(m, bool)
        mask[:k] = True
        return mask
    mask = np.asarray(phase1, bool)
    if mask.shape != (m,):
        raise ValueError("phase1 mask must have one entry per point")
    return mask


def _excl_mask(exclude: Iterable[int], m: int) -> np.ndarray:
    mask = np.zeros(m, bool)
    for i in exclude or ():
        if not -m <= int(i) < m:
            raise IndexError(f"exclude position {i} out of range")
        mask[int(i)] = True
    return mask


def _fit_with_revision(
    fit: Callable[[np.ndarray], list[ChartResult]],
    phase1: np.ndarray,
    excluded: np.ndarray,
    revise: bool,
    max_iter: int = 25,
) -> list[ChartResult]:
    """Fit charts; optionally drop Phase I rule-1 points and refit until stable."""
    excluded = excluded.copy()
    for _ in range(max_iter):
        if (phase1 & ~excluded).sum() < 2:
            raise ValueError("fewer than 2 points left to estimate limits")
        results = fit(excluded)
        if not revise:
            return results
        new = np.zeros_like(excluded)
        for r in results:
            beyond = (r.statistic > r.ucl + 1e-12) | (r.statistic < r.lcl - 1e-12)
            new |= beyond & phase1 & ~excluded
        if not new.any():
            return results
        excluded |= new
    return results


def _finish(res: ChartResult, rules, run_length: int) -> ChartResult:
    res.violations = evaluate(res.statistic, res.center, res.sigma, res.ucl, res.lcl,
                              rules=rules, run_length=run_length)
    return res


# ---------------------------------------------------------------------------
# variables charts
# ---------------------------------------------------------------------------

def xbar_r(
    data,
    *,
    phase1=None,
    exclude: Sequence[int] = (),
    revise: bool = False,
    mu: float | None = None,
    sigma: float | None = None,
    L: float = 3.0,
    rules="nelson",
    dispersion_rules=(1,),
    run_length: int = 9,
    labels=None,
) -> tuple[ChartResult, ChartResult]:
    """X̄ and R charts for subgroups of equal size n (2 ≤ n ≤ 50; best for n ≤ 10).

    ``data``: rows are subgroups, columns are the n measurements.
    σ is estimated by R̄/d2 over the Phase I subgroups.
    """
    rows = _subgroups(data)
    sizes = np.array([r.size for r in rows])
    if np.unique(sizes).size != 1:
        raise ValueError("X̄-R needs equal subgroup sizes; use xbar_s() for unequal sizes")
    n = int(sizes[0])
    if n < 2:
        raise ValueError("subgroups need at least 2 observations; use imr() for individuals")
    m = len(rows)
    xbar = np.array([r.mean() for r in rows])
    rng = np.array([r.max() - r.min() for r in rows])
    p1 = _phase_mask(phase1, m)
    idx = _labels(data, m, labels)
    d2, d3 = K.d2(n), K.d3(n)

    def fit(excl):
        use = p1 & ~excl
        s = sigma if sigma is not None else rng[use].mean() / d2
        mu_ = mu if mu is not None else xbar[use].mean()
        se = s / np.sqrt(n)
        xr = ChartResult("Xbar", xbar, mu_, mu_ + L * se, mu_ - L * se, se, idx, p1, excl,
                         params=dict(mu=mu_, sigma=s, n=n, L=L, sigma_method="Rbar/d2"))
        rr = ChartResult("R", rng, d2 * s, (d2 + L * d3) * s, max(0.0, (d2 - L * d3) * s), d3 * s,
                         idx, p1, excl, params=dict(Rbar=d2 * s, sigma=s, n=n, L=L))
        return [xr, rr]

    xr, rr = _fit_with_revision(fit, p1, _excl_mask(exclude, m), revise)
    return _finish(xr, rules, run_length), _finish(rr, dispersion_rules, run_length)


def _pooled_sigma(s: np.ndarray, n: np.ndarray) -> float:
    if np.unique(n).size == 1:
        return s.mean() / K.c4(int(n[0]))
    df = (n - 1).sum()
    sp = np.sqrt(((n - 1) * s**2).sum() / df)
    return sp / K.c4(int(df) + 1)


def xbar_s(
    data,
    *,
    phase1=None,
    exclude: Sequence[int] = (),
    revise: bool = False,
    mu: float | None = None,
    sigma: float | None = None,
    L: float = 3.0,
    rules="nelson",
    dispersion_rules=(1,),
    run_length: int = 9,
    labels=None,
) -> tuple[ChartResult, ChartResult]:
    """X̄ and S charts; subgroup sizes may differ (limits then vary by subgroup).

    σ is estimated by s̄/c4 (equal n) or the pooled standard deviation / c4
    (unequal n).
    """
    rows = _subgroups(data)
    n = np.array([r.size for r in rows])
    if (n < 2).any():
        raise ValueError("every subgroup needs at least 2 observations")
    m = len(rows)
    xbar = np.array([r.mean() for r in rows])
    s = np.array([r.std(ddof=1) for r in rows])
    c4 = np.array([K.c4(int(k)) for k in n])
    p1 = _phase_mask(phase1, m)
    idx = _labels(data, m, labels)

    def fit(excl):
        use = p1 & ~excl
        sig = sigma if sigma is not None else _pooled_sigma(s[use], n[use])
        mu_ = mu if mu is not None else np.average(xbar[use], weights=n[use])
        se = sig / np.sqrt(n)
        xr = ChartResult("Xbar", xbar, mu_, mu_ + L * se, mu_ - L * se, se, idx, p1, excl,
                         params=dict(mu=mu_, sigma=sig, n=n, L=L, sigma_method="Sbar/c4"))
        ss = sig * np.sqrt(1 - c4**2)
        sr = ChartResult("S", s, c4 * sig, c4 * sig + L * ss, np.maximum(0, c4 * sig - L * ss), ss,
                         idx, p1, excl, params=dict(sigma=sig, n=n, L=L))
        return [xr, sr]

    xr, sr = _fit_with_revision(fit, p1, _excl_mask(exclude, m), revise)
    return _finish(xr, rules, run_length), _finish(sr, dispersion_rules, run_length)


def _mr_sigma(x: np.ndarray, use: np.ndarray, method: str) -> float:
    mr = np.abs(np.diff(x))
    ok = use[1:] & use[:-1] & np.isfinite(mr)
    if ok.sum() < 1:
        raise ValueError("not enough consecutive points to estimate sigma from moving ranges")
    if method == "mr":
        return mr[ok].mean() / K.d2(2)
    if method == "median_mr":
        return np.median(mr[ok]) / 0.954  # median of MR(2) ≈ 0.954σ
    if method == "sd":
        return np.nanstd(x[use], ddof=1) / K.c4(int(np.isfinite(x[use]).sum()))
    raise ValueError("sigma_method must be 'mr', 'median_mr' or 'sd'")


def imr(
    x,
    *,
    phase1=None,
    exclude: Sequence[int] = (),
    revise: bool = False,
    mu: float | None = None,
    sigma: float | None = None,
    sigma_method: str = "mr",
    L: float = 3.0,
    rules="nelson",
    dispersion_rules=(1,),
    run_length: int = 9,
    labels=None,
) -> tuple[ChartResult, ChartResult]:
    """Individuals (I) and moving-range (MR) charts for one observation per period.

    σ is estimated by MR̄/1.128 (``sigma_method="mr"``), median MR/0.954
    (``"median_mr"``, robust to a few outliers) or the overall standard
    deviation (``"sd"``, *not* recommended: inflated by shifts and trends).
    """
    xs = pd.Series(x) if not isinstance(x, pd.Series) else x
    v = xs.to_numpy(dtype=float)
    m = v.size
    if m < 3:
        raise ValueError("need at least 3 observations")
    p1 = _phase_mask(phase1, m)
    idx = _labels(x, m, labels)
    mr = np.concatenate([[np.nan], np.abs(np.diff(v))])
    d2, d3 = K.d2(2), K.d3(2)

    def fit(excl):
        use = p1 & ~excl & np.isfinite(v)
        sig = sigma if sigma is not None else _mr_sigma(v, use, sigma_method)
        mu_ = mu if mu is not None else v[use].mean()
        ir = ChartResult("I", v, mu_, mu_ + L * sig, mu_ - L * sig, sig, idx, p1, excl,
                         params=dict(mu=mu_, sigma=sig, L=L, sigma_method=sigma_method))
        mrr = ChartResult("MR", mr, d2 * sig, (d2 + L * d3) * sig, max(0.0, (d2 - L * d3) * sig),
                          d3 * sig, idx, p1, excl, params=dict(MRbar=d2 * sig, sigma=sig, L=L))
        return [ir, mrr]

    ir, mrr = _fit_with_revision(fit, p1, _excl_mask(exclude, m), revise)
    # moving ranges are autocorrelated: zone/run rules are not meaningful there
    return _finish(ir, rules, run_length), _finish(mrr, dispersion_rules, run_length)


# ---------------------------------------------------------------------------
# attributes charts
# ---------------------------------------------------------------------------

def _laney_factor(z: np.ndarray, use: np.ndarray) -> float:
    """σ_z from the average moving range of standardized values (Laney 2002)."""
    mr = np.abs(np.diff(z))
    ok = use[1:] & use[:-1] & np.isfinite(mr)
    return float(mr[ok].mean() / K.d2(2))


def _attr_result(name, stat, cl, se, L, idx, p1, excl, params, upper=None):
    ucl = cl + L * se
    if upper is not None:
        ucl = np.minimum(ucl, upper)
    lcl = np.maximum(0.0, cl - L * se)
    return ChartResult(name, stat, cl, ucl, lcl, se, idx, p1, excl, params=params, kind="attribute")


def p_chart(
    defectives,
    sizes,
    *,
    phase1=None,
    exclude: Sequence[int] = (),
    revise: bool = False,
    p: float | None = None,
    laney: bool = False,
    L: float = 3.0,
    rules="attribute",
    run_length: int = 9,
    labels=None,
) -> ChartResult:
    """Proportion-nonconforming chart; ``sizes`` may vary (limits then vary).

    ``laney=True`` gives Laney's p′ chart, which widens the limits when the
    data are over-dispersed relative to the binomial model — common with very
    large samples (thousands of invoices, calls, transactions), where a
    standard p chart flags almost every point. ``params["sigma_z"]`` is
    always reported: values well above 1 indicate overdispersion.
    """
    d = np.asarray(defectives, float)
    n = np.broadcast_to(np.asarray(sizes, float), d.shape).astype(float)
    if (d < 0).any() or (d > n).any():
        raise ValueError("defectives must be between 0 and the sample size")
    m = d.size
    p1 = _phase_mask(phase1, m)
    idx = _labels(defectives, m, labels)
    phat = d / n

    def fit(excl):
        use = p1 & ~excl
        pbar = p if p is not None else d[use].sum() / n[use].sum()
        if not 0 < pbar < 1:
            raise ValueError("average proportion is 0 or 1; a p chart cannot be built")
        se = np.sqrt(pbar * (1 - pbar) / n)
        sz = _laney_factor((phat - pbar) / se, use)
        if laney:
            se = se * sz
        name = "p'" if laney else "p"
        return [_attr_result(name, phat, pbar, se, L, idx, p1, excl,
                             dict(pbar=pbar, n=n, L=L, laney=laney, sigma_z=sz), upper=1.0)]

    (res,) = _fit_with_revision(fit, p1, _excl_mask(exclude, m), revise)
    return _finish(res, rules, run_length)


def np_chart(
    defectives,
    n: int,
    *,
    phase1=None,
    exclude: Sequence[int] = (),
    revise: bool = False,
    p: float | None = None,
    L: float = 3.0,
    rules="attribute",
    run_length: int = 9,
    labels=None,
) -> ChartResult:
    """Number-nonconforming chart for a constant sample size ``n``."""
    d = np.asarray(defectives, float)
    if (d < 0).any() or (d > n).any():
        raise ValueError(f"defectives must be between 0 and the sample size n = {n}")
    m = d.size
    p1 = _phase_mask(phase1, m)
    idx = _labels(defectives, m, labels)

    def fit(excl):
        use = p1 & ~excl
        pbar = p if p is not None else d[use].sum() / (n * use.sum())
        if not 0 < pbar < 1:
            raise ValueError("average proportion is 0 or 1; an np chart cannot be built")
        se = np.sqrt(n * pbar * (1 - pbar))
        return [_attr_result("np", d, n * pbar, se, L, idx, p1, excl,
                             dict(pbar=pbar, n=n, L=L), upper=float(n))]

    (res,) = _fit_with_revision(fit, p1, _excl_mask(exclude, m), revise)
    return _finish(res, rules, run_length)


def c_chart(
    counts,
    *,
    phase1=None,
    exclude: Sequence[int] = (),
    revise: bool = False,
    c: float | None = None,
    L: float = 3.0,
    rules="attribute",
    run_length: int = 9,
    labels=None,
) -> ChartResult:
    """Count-of-defects chart for a constant area of opportunity (Poisson)."""
    x = np.asarray(counts, float)
    m = x.size
    p1 = _phase_mask(phase1, m)
    idx = _labels(counts, m, labels)

    def fit(excl):
        use = p1 & ~excl
        cbar = c if c is not None else x[use].mean()
        return [_attr_result("c", x, cbar, np.sqrt(cbar), L, idx, p1, excl, dict(cbar=cbar, L=L))]

    (res,) = _fit_with_revision(fit, p1, _excl_mask(exclude, m), revise)
    return _finish(res, rules, run_length)


def u_chart(
    counts,
    units,
    *,
    phase1=None,
    exclude: Sequence[int] = (),
    revise: bool = False,
    u: float | None = None,
    laney: bool = False,
    L: float = 3.0,
    rules="attribute",
    run_length: int = 9,
    labels=None,
) -> ChartResult:
    """Defects-per-unit chart; ``units`` (area of opportunity) may vary.

    ``laney=True`` gives Laney's u′ chart for over-dispersed counts.
    """
    x = np.asarray(counts, float)
    a = np.broadcast_to(np.asarray(units, float), x.shape).astype(float)
    if (a <= 0).any():
        raise ValueError("units must be positive")
    m = x.size
    p1 = _phase_mask(phase1, m)
    idx = _labels(counts, m, labels)
    rate = x / a

    def fit(excl):
        use = p1 & ~excl
        ubar = u if u is not None else x[use].sum() / a[use].sum()
        se = np.sqrt(ubar / a)
        sz = _laney_factor((rate - ubar) / se, use)
        if laney:
            se = se * sz
        name = "u'" if laney else "u"
        return [_attr_result(name, rate, ubar, se, L, idx, p1, excl,
                             dict(ubar=ubar, units=a, L=L, laney=laney, sigma_z=sz))]

    (res,) = _fit_with_revision(fit, p1, _excl_mask(exclude, m), revise)
    return _finish(res, rules, run_length)


# ---------------------------------------------------------------------------
# time-weighted charts
# ---------------------------------------------------------------------------

def _location_scale(v, p1, excl, mu, sigma, sigma_method):
    use = p1 & ~excl & np.isfinite(v)
    sig = sigma if sigma is not None else _mr_sigma(v, use, sigma_method)
    mu_ = mu if mu is not None else v[use].mean()
    return mu_, sig


def ewma(
    x,
    *,
    lam: float = 0.2,
    L: float = 3.0,
    phase1=None,
    exclude: Sequence[int] = (),
    mu: float | None = None,
    sigma: float | None = None,
    sigma_method: str = "mr",
    asymptotic: bool = False,
    labels=None,
) -> ChartResult:
    """Exponentially weighted moving average chart for individual values.

    z_i = λ x_i + (1 − λ) z_{i−1},  z_0 = μ0.
    Limits μ0 ± Lσ sqrt(λ/(2−λ) [1 − (1−λ)^{2i}]) (exact, narrower at the
    start) or the asymptotic version. Smaller λ detects smaller shifts.
    Lucas & Saccucci (1990): λ=0.2, L=2.962 gives in-control ARL ≈ 500.

    To chart subgroup means, pass the means and ``sigma = σ/√n``.
    """
    if not 0 < lam <= 1:
        raise ValueError("lam must be in (0, 1]")
    xs = pd.Series(x) if not isinstance(x, pd.Series) else x
    v = xs.to_numpy(dtype=float)
    m = v.size
    p1 = _phase_mask(phase1, m)
    excl = _excl_mask(exclude, m)
    idx = _labels(x, m, labels)
    mu0, sig = _location_scale(v, p1, excl, mu, sigma, sigma_method)

    z = np.empty(m)
    prev = mu0
    for i, xi in enumerate(v):
        prev = prev if not np.isfinite(xi) else lam * xi + (1 - lam) * prev
        z[i] = prev
    i = np.arange(1, m + 1)
    factor = lam / (2 - lam) * (np.ones(m) if asymptotic else 1 - (1 - lam) ** (2 * i))
    se = sig * np.sqrt(factor)
    res = ChartResult("EWMA", z, mu0, mu0 + L * se, mu0 - L * se, se, idx, p1, excl,
                      params=dict(mu=mu0, sigma=sig, lam=lam, L=L), extra=dict(x=v), kind="ewma")
    return _finish(res, (1,), 9)


def cusum(
    x,
    *,
    k: float = 0.5,
    h: float = 5.0,
    phase1=None,
    exclude: Sequence[int] = (),
    mu: float | None = None,
    sigma: float | None = None,
    sigma_method: str = "mr",
    fir: float = 0.0,
    labels=None,
) -> ChartResult:
    """Tabular (two-sided) CUSUM for individual values.

    C⁺_i = max(0, x_i − (μ0 + K) + C⁺_{i−1}),  C⁻_i = max(0, (μ0 − K) − x_i + C⁻_{i−1})
    with K = kσ and decision interval H = hσ. k = 0.5 is tuned to detect a
    1σ shift; h = 5 gives an in-control ARL of about 465 (h = 4: about 168).
    ``fir`` (fast initial response) starts both sums at ``fir * H``
    (Lucas & Crosier 1982 suggest 0.5).

    The returned ``statistic`` is C⁺; ``extra["C_minus"]`` holds −C⁻ so both
    can be drawn on one chart. ``extra["shift_estimate"]`` gives the
    estimated new mean at each signal.
    """
    xs = pd.Series(x) if not isinstance(x, pd.Series) else x
    v = xs.to_numpy(dtype=float)
    m = v.size
    p1 = _phase_mask(phase1, m)
    excl = _excl_mask(exclude, m)
    idx = _labels(x, m, labels)
    mu0, sig = _location_scale(v, p1, excl, mu, sigma, sigma_method)
    Kv, H = k * sig, h * sig

    cp = np.zeros(m)
    cm = np.zeros(m)
    np_ = np.zeros(m, int)
    nm = np.zeros(m, int)
    a = b = fir * H
    na = nb = 0
    for i, xi in enumerate(v):
        if np.isfinite(xi):
            a = max(0.0, xi - (mu0 + Kv) + a)
            b = max(0.0, (mu0 - Kv) - xi + b)
            na = na + 1 if a > 0 else 0
            nb = nb + 1 if b > 0 else 0
        cp[i], cm[i], np_[i], nm[i] = a, b, na, nb

    sig_up = np.flatnonzero(cp > H)
    sig_dn = np.flatnonzero(cm > H)
    with np.errstate(invalid="ignore", divide="ignore"):
        est = np.where(cp > H, mu0 + Kv + cp / np.maximum(np_, 1),
                       np.where(cm > H, mu0 - Kv - cm / np.maximum(nm, 1), np.nan))
    res = ChartResult(
        "CUSUM", cp, 0.0, H, -H, sig, idx, p1, excl,
        params=dict(mu=mu0, sigma=sig, k=k, h=h, K=Kv, H=H, fir=fir),
        extra=dict(C_minus=-cm, N_plus=np_, N_minus=nm, x=v, shift_estimate=est),
        kind="cusum",
    )
    res.violations = {1: np.union1d(sig_up, sig_dn)}
    return res
