"""Average run length (ARL): how quickly does a chart notice a shift?

ARL0 (no shift) is the average number of points between false alarms;
ARL1 (after a shift of δσ in the mean) is the average delay to detection.
A good chart has a large ARL0 and a small ARL1. This module computes them by
exact formula (Shewhart, rule 1 only) or Monte Carlo simulation, for
individual standard-normal observations with known parameters.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .rules import evaluate


def shewhart_arl(shift: float, L: float = 3.0) -> float:
    """Exact ARL of an individuals/X̄ chart with rule 1 only (shift in σ of the plotted statistic)."""
    p = stats.norm.sf(L - shift) + stats.norm.cdf(-L - shift)
    return float(1.0 / p)


def _ewma_rl(shift, reps, rng, lam, L, max_len):
    z = np.zeros(reps)
    rl = np.full(reps, max_len)
    alive = np.ones(reps, bool)
    a = lam / (2 - lam)
    for t in range(1, max_len + 1):
        x = rng.standard_normal(reps) + shift
        z = lam * x + (1 - lam) * z
        lim = L * np.sqrt(a * (1 - (1 - lam) ** (2 * t)))
        hit = alive & (np.abs(z) > lim)
        rl[hit] = t
        alive &= ~hit
        if not alive.any():
            break
    return rl


def _cusum_rl(shift, reps, rng, k, h, max_len, fir=0.0):
    cp = np.full(reps, fir * h)
    cm = np.full(reps, fir * h)
    rl = np.full(reps, max_len)
    alive = np.ones(reps, bool)
    for t in range(1, max_len + 1):
        x = rng.standard_normal(reps) + shift
        cp = np.maximum(0, x - k + cp)
        cm = np.maximum(0, -k - x + cm)
        hit = alive & ((cp > h) | (cm > h))
        rl[hit] = t
        alive &= ~hit
        if not alive.any():
            break
    return rl


def _shewhart_rules_rl(shift, reps, rng, rules, run_length, max_len):
    rl = np.full(reps, max_len)
    for r in range(reps):
        x = rng.standard_normal(max_len) + shift
        v = evaluate(x, 0.0, 1.0, rules=rules, run_length=run_length)
        hits = np.concatenate([a for a in v.values()]) if v else np.array([])
        if hits.size:
            rl[r] = int(hits.min()) + 1
    return rl


def run_lengths(
    chart: str,
    shift: float,
    *,
    reps: int = 2000,
    seed: int | None = 0,
    max_len: int = 5000,
    lam: float = 0.2,
    L: float = 3.0,
    k: float = 0.5,
    h: float = 5.0,
    fir: float = 0.0,
    rules="limits",
    run_length: int = 9,
) -> np.ndarray:
    """Simulated run lengths for ``chart`` in {"shewhart", "ewma", "cusum"}.

    ``shift`` is the step change in the mean, in units of σ, present from the
    first observation. Runs that never signal are censored at ``max_len``.
    """
    rng = np.random.default_rng(seed)
    if chart == "ewma":
        return _ewma_rl(shift, reps, rng, lam, L, max_len)
    if chart == "cusum":
        return _cusum_rl(shift, reps, rng, k, h, max_len, fir)
    if chart == "shewhart":
        if rules in ("limits", (1,), [1]):
            return rng.geometric(1 / shewhart_arl(shift, L), size=reps).clip(max=max_len)
        return _shewhart_rules_rl(shift, reps, rng, rules, run_length, max_len)
    raise ValueError("chart must be 'shewhart', 'ewma' or 'cusum'")


def compare(
    shifts=(0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0),
    *,
    reps: int = 2000,
    seed: int = 0,
    lam: float = 0.2,
    L_ewma: float = 2.962,
    k: float = 0.5,
    h: float = 5.0,
) -> pd.DataFrame:
    """ARL table comparing Shewhart (exact), Shewhart + WE rules, EWMA and CUSUM."""
    rows = []
    for d in shifts:
        rows.append(
            {
                "shift (σ)": d,
                "Shewhart": shewhart_arl(d),
                "Shewhart + WE rules": run_lengths("shewhart", d, reps=max(200, reps // 4), seed=seed,
                                                   rules="western_electric", run_length=8, max_len=3000).mean(),
                f"EWMA (λ={lam}, L={L_ewma})": run_lengths("ewma", d, reps=reps, seed=seed, lam=lam, L=L_ewma).mean(),
                f"CUSUM (k={k}, h={h})": run_lengths("cusum", d, reps=reps, seed=seed, k=k, h=h).mean(),
            }
        )
    return pd.DataFrame(rows).set_index("shift (σ)")
