"""Process capability analysis (normal model).

*Within* (short-term) indices Cp, Cpk use σ estimated from within-subgroup
variation (R̄/d2, s̄/c4 or MR̄/1.128). *Overall* (long-term) indices Pp, Ppk
use the ordinary sample standard deviation. A large gap between the two says
the process is not stable — between-subgroup shifts are inflating the overall
spread — and capability numbers should not be trusted until it is.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from . import constants as K
from .charts import _subgroups


@dataclass
class CapabilityResult:
    n: int
    mean: float
    sigma_within: float
    sigma_overall: float
    lsl: float | None
    usl: float | None
    target: float | None
    indices: dict[str, float]
    intervals: dict[str, tuple[float, float]]
    ppm: pd.DataFrame
    normality: dict[str, float]
    data: np.ndarray = field(repr=False)
    sigma_method: str = "MRbar/d2"
    confidence: float = 0.95

    def to_frame(self) -> pd.DataFrame:
        rows = []
        for k, v in self.indices.items():
            lo, hi = self.intervals.get(k, (np.nan, np.nan))
            rows.append(dict(index=k, estimate=v, lower=lo, upper=hi))
        return pd.DataFrame(rows).set_index("index")

    def interpretation(self) -> str:
        """Plain-language reading of the main results."""
        msgs = []
        cpk = self.indices.get("Cpk", np.nan)
        ppk = self.indices.get("Ppk", np.nan)
        cp = self.indices.get("Cp", np.nan)
        if np.isfinite(cpk):
            if cpk >= 1.67:
                msgs.append(f"Cpk = {cpk:.2f}: highly capable (≥ 1.67 is the usual target for critical or new processes).")
            elif cpk >= 1.33:
                msgs.append(f"Cpk = {cpk:.2f}: capable (≥ 1.33 is the common minimum for existing processes).")
            elif cpk >= 1.0:
                msgs.append(f"Cpk = {cpk:.2f}: marginal; roughly {self.ppm.loc['expected (within)', 'total']:,.0f} PPM expected outside spec.")
            else:
                msgs.append(f"Cpk = {cpk:.2f}: not capable; the process will produce out-of-spec output routinely.")
        if np.isfinite(cp) and np.isfinite(cpk) and cp - cpk > 0.2:
            msgs.append(f"Cp ({cp:.2f}) is well above Cpk ({cpk:.2f}): the spread is acceptable but the process is "
                        "off-center. Re-centering is the cheapest improvement.")
        if np.isfinite(cpk) and np.isfinite(ppk) and cpk > 0 and (cpk - ppk) / cpk > 0.15:
            msgs.append(f"Ppk ({ppk:.2f}) is much lower than Cpk: variation between subgroups (shifts, drift) "
                        "is inflating the long-term spread. Check the control chart for stability first.")
        if self.normality.get("p_value", 1.0) < 0.05:
            msgs.append(f"Normality is doubtful ({self.normality['test']} p = {self.normality['p_value']:.3f}); "
                        "the PPM estimates and indices assume a normal distribution and may be misleading.")
        if self.n < 30:
            msgs.append(f"Only {self.n} observations: confidence intervals are wide, so treat the indices as rough.")
        return "\n".join(msgs)

    def plot(self, ax=None, **kwargs):
        from .plotting import plot_capability

        return plot_capability(self, ax=ax, **kwargs)


def _cp_interval(cp, df, conf):
    a = 1 - conf
    return (cp * np.sqrt(stats.chi2.ppf(a / 2, df) / df), cp * np.sqrt(stats.chi2.ppf(1 - a / 2, df) / df))


def _cpk_interval(cpk, n, conf):
    # Bissell (1990) normal approximation
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    se = np.sqrt(1 / (9 * n) + cpk**2 / (2 * (n - 1)))
    return (cpk - z * se, cpk + z * se)


def capability(
    data,
    lsl: float | None = None,
    usl: float | None = None,
    *,
    target: float | None = None,
    subgrouped: bool | None = None,
    confidence: float = 0.95,
) -> CapabilityResult:
    """Capability indices, confidence intervals, PPM and a normality check.

    Parameters
    ----------
    data : 1-D array of individual values, or 2-D (rows = subgroups)
    lsl, usl : specification limits (at least one is required)
    target : target value for Cpm (defaults to the spec midpoint when both specs exist)
    subgrouped : force interpretation; by default 2-D input is treated as subgroups
    """
    if lsl is None and usl is None:
        raise ValueError("give at least one specification limit")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("LSL must be below USL")

    if subgrouped is None:
        if isinstance(data, pd.DataFrame):
            subgrouped = data.select_dtypes("number").shape[1] > 1
        elif isinstance(data, pd.Series):
            subgrouped = False
        elif isinstance(data, np.ndarray):
            subgrouped = data.ndim == 2 and min(data.shape) > 1
        else:
            subgrouped = len(data) > 0 and np.ndim(data[0]) == 1

    if subgrouped:
        rows = _subgroups(data)
        x = np.concatenate(rows)
        n_i = np.array([r.size for r in rows])
        if (n_i < 2).any():
            raise ValueError("subgroups need at least 2 observations")
        if np.unique(n_i).size == 1 and n_i[0] <= 10:
            sw = np.mean([r.max() - r.min() for r in rows]) / K.d2(int(n_i[0]))
            method = "Rbar/d2"
        else:
            s = np.array([r.std(ddof=1) for r in rows])
            df = (n_i - 1).sum()
            sw = np.sqrt(((n_i - 1) * s**2).sum() / df) / K.c4(int(df) + 1)
            method = "pooled s/c4"
    else:
        x = np.asarray(data, float).ravel()
        x = x[np.isfinite(x)]
        sw = np.abs(np.diff(x)).mean() / K.d2(2)
        method = "MRbar/d2"

    n = x.size
    if n < 5:
        raise ValueError("need at least 5 observations")
    mean = x.mean()
    so = x.std(ddof=1)
    if target is None and lsl is not None and usl is not None:
        target = (lsl + usl) / 2

    idx: dict[str, float] = {}
    ci: dict[str, tuple[float, float]] = {}
    for tag, sig in (("C", sw), ("P", so)):
        if lsl is not None and usl is not None:
            idx[f"{tag}p"] = (usl - lsl) / (6 * sig)
        if usl is not None:
            idx[f"{tag}pu"] = (usl - mean) / (3 * sig)
        if lsl is not None:
            idx[f"{tag}pl"] = (mean - lsl) / (3 * sig)
        idx[f"{tag}pk"] = min(v for k, v in idx.items() if k in (f"{tag}pu", f"{tag}pl"))
    if target is not None and lsl is not None and usl is not None:
        idx["Cpm"] = (usl - lsl) / (6 * np.sqrt(so**2 + (mean - target) ** 2))

    if "Cp" in idx:
        ci["Cp"] = _cp_interval(idx["Cp"], n - 1, confidence)
        ci["Pp"] = _cp_interval(idx["Pp"], n - 1, confidence)
    ci["Cpk"] = _cpk_interval(idx["Cpk"], n, confidence)
    ci["Ppk"] = _cpk_interval(idx["Ppk"], n, confidence)

    def ppm_row(sig):
        lo = stats.norm.cdf((lsl - mean) / sig) * 1e6 if lsl is not None else 0.0
        hi = stats.norm.sf((usl - mean) / sig) * 1e6 if usl is not None else 0.0
        return dict(below_LSL=lo, above_USL=hi, total=lo + hi)

    obs = dict(
        below_LSL=(x < lsl).mean() * 1e6 if lsl is not None else 0.0,
        above_USL=(x > usl).mean() * 1e6 if usl is not None else 0.0,
    )
    obs["total"] = obs["below_LSL"] + obs["above_USL"]
    ppm = pd.DataFrame(
        [obs, ppm_row(sw), ppm_row(so)], index=["observed", "expected (within)", "expected (overall)"]
    )
    # Z.bench: the one-sided z equivalent to the total expected nonconforming fraction
    tot = ppm.loc["expected (overall)", "total"] / 1e6
    idx["Z.bench (overall)"] = float(stats.norm.isf(tot)) if 0 < tot < 1 else np.inf

    if n <= 5000:
        w, pval = stats.shapiro(x)
        normality = dict(test="Shapiro-Wilk", statistic=float(w), p_value=float(pval))
    else:
        ad = stats.anderson(x, dist="norm")
        normality = dict(test="Anderson-Darling", statistic=float(ad.statistic),
                         p_value=float("nan"))

    return CapabilityResult(n, mean, sw, so, lsl, usl, target, idx, ci, ppm, normality, x, method, confidence)
