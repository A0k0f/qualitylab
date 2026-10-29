"""Hotelling T² chart for individual multivariate observations.

Phase I (retrospective) limits use the beta distribution (Tracy, Young &
Mason 1992); Phase II limits for new observations use the F distribution.
The covariance can be the ordinary sample covariance or the successive-
difference estimator of Sullivan & Woodall (1996), which is much less
inflated by a sustained shift in the Phase I data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .result import ChartResult


def _successive_difference_cov(X: np.ndarray) -> np.ndarray:
    V = np.diff(X, axis=0)
    return V.T @ V / (2 * (X.shape[0] - 1))


def hotelling_t2(
    X,
    *,
    phase1: int | None = None,
    alpha: float = 0.0027,
    cov: str = "sample",
    labels=None,
) -> ChartResult:
    """T² chart.

    Parameters
    ----------
    X : (m, p) array or DataFrame of individual observations
    phase1 : number of initial rows used to estimate the mean and covariance;
        None = all (pure Phase I). Points after it get Phase II (F) limits.
    alpha : false-alarm probability per point (0.0027 matches 3σ Shewhart).
    cov : "sample" or "successive_difference".

    ``extra["contributions"]`` gives each variable's share of the squared
    standardized deviations at every point. It ignores correlation, so it is
    a quick first look at *which* variables moved, not an exact T²
    decomposition (for that, see Mason, Tracy & Young 1995).
    """
    df = X if isinstance(X, pd.DataFrame) else pd.DataFrame(np.asarray(X, float))
    A = df.to_numpy(dtype=float)
    if np.isnan(A).any():
        raise ValueError("T² needs complete rows; impute or drop missing values first")
    m_all, p = A.shape
    m = m_all if phase1 is None else int(phase1)
    if m <= p + 1:
        raise ValueError(f"need more than p+1 = {p + 1} Phase I observations (have {m})")
    ref = A[:m]
    mean = ref.mean(axis=0)
    if cov == "sample":
        S = np.cov(ref, rowvar=False)
    elif cov == "successive_difference":
        S = _successive_difference_cov(ref)
    else:
        raise ValueError("cov must be 'sample' or 'successive_difference'")
    Sinv = np.linalg.pinv(S)
    D = A - mean
    t2 = np.einsum("ij,jk,ik->i", D, Sinv, D)

    ucl1 = (m - 1) ** 2 / m * stats.beta.ppf(1 - alpha, p / 2, (m - p - 1) / 2)
    ucl2 = p * (m + 1) * (m - 1) / (m * m - m * p) * stats.f.ppf(1 - alpha, p, m - p)
    is_p1 = np.arange(m_all) < m
    ucl = np.where(is_p1, ucl1, ucl2)

    sd = np.sqrt(np.diag(S))
    contrib = (D / sd) ** 2
    contrib = contrib / contrib.sum(axis=1, keepdims=True)

    idx = pd.Index(labels) if labels is not None else (df.index if isinstance(X, pd.DataFrame) else pd.RangeIndex(1, m_all + 1))
    res = ChartResult(
        "T²", t2, np.full(m_all, p * (m - 1) / m), ucl, np.zeros(m_all), np.full(m_all, np.nan),
        idx, is_p1,
        params=dict(p=p, m=m, alpha=alpha, cov=cov, mean=mean, S=S),
        extra=dict(contributions=pd.DataFrame(contrib, index=idx, columns=df.columns)),
        kind="t2",
    )
    res.violations = {1: np.flatnonzero(t2 > ucl)}
    return res
