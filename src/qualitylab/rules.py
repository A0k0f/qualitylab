"""Run rules for detecting special-cause patterns (Nelson / Western Electric).

Numbering follows Nelson (1984) and Minitab's "Tests for Special Causes":

1. One point beyond the control limits (3σ).
2. *k* points in a row on the same side of the center line (Nelson k=9, WE k=8).
3. 6 points in a row steadily increasing or decreasing.
4. 14 points in a row alternating up and down.
5. 2 of 3 consecutive points beyond 2σ, same side.
6. 4 of 5 consecutive points beyond 1σ, same side.
7. 15 points in a row within 1σ of the center line (either side).
8. 8 points in a row beyond 1σ (either side), none within 1σ.

A violation is reported at the point that *completes* the pattern, which is
the moment an operator watching the chart in real time would react.
Missing values (NaN) break runs.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

RULE_DESCRIPTIONS = {
    1: "point beyond a control limit",
    2: "run of points on one side of the center line",
    3: "6 points in a row trending up or down",
    4: "14 points in a row alternating up and down",
    5: "2 of 3 points beyond 2σ on the same side",
    6: "4 of 5 points beyond 1σ on the same side",
    7: "15 points in a row within 1σ (stratification)",
    8: "8 points in a row beyond 1σ on either side (mixture)",
}

PRESETS: dict[str, tuple[int, ...]] = {
    "limits": (1,),
    "attribute": (1, 2, 3, 4),
    "western_electric": (1, 2, 5, 6),
    "nelson": (1, 2, 3, 4, 5, 6, 7, 8),
}

PLAIN_LANGUAGE = {
    1: "Something unusual happened at this point. Look for a special cause right here.",
    2: "The process average has probably shifted. Look for a change shortly before the run began.",
    3: "The process is drifting (tool wear, fatigue, temperature, a growing backlog...).",
    4: "Systematic alternation: two machines, shifts or suppliers feeding the process in turn, or over-adjustment.",
    5: "An early warning of a shift in the average.",
    6: "A smaller sustained shift in the average.",
    7: "Too little variation for these limits: limits may be wrong, or data come from mixed/stratified sources.",
    8: "Points avoid the center: a mixture of two processes (e.g., two operators with different settings).",
}


def _runs(mask: np.ndarray) -> np.ndarray:
    """Length of the current run of True values ending at each position."""
    out = np.zeros(mask.size, dtype=int)
    c = 0
    for i, m in enumerate(mask):
        c = c + 1 if m else 0
        out[i] = c
    return out


def _k_of_m(flag: np.ndarray, k: int, m: int) -> np.ndarray:
    """Positions i where at least k of flag[i-m+1..i] are True and flag[i] is True.

    At the start of the series the window is whatever is available.
    """
    hits = []
    csum = np.concatenate([[0], np.cumsum(flag.astype(int))])
    for i in range(k - 1, flag.size):
        if flag[i] and csum[i + 1] - csum[max(0, i + 1 - m)] >= k:
            hits.append(i)
    return np.asarray(hits, dtype=int)


def evaluate(
    statistic: Sequence[float],
    center: Sequence[float],
    sigma: Sequence[float],
    ucl: Sequence[float] | None = None,
    lcl: Sequence[float] | None = None,
    rules: Iterable[int] | str = "nelson",
    run_length: int = 9,
) -> dict[int, np.ndarray]:
    """Evaluate run rules.

    Parameters
    ----------
    statistic, center, sigma : array-like
        Plotted values, center line and the standard error of the plotted
        statistic at each point. Zones are center ± 1σ, 2σ.
    ucl, lcl : array-like, optional
        Control limits for rule 1. Default: center ± 3σ.
    rules : iterable of int or preset name
        ``"limits"``, ``"western_electric"``, ``"nelson"`` or e.g. ``[1, 2, 5]``.
    run_length : int
        k for rule 2 (9 = Nelson/Minitab, 8 = Western Electric).

    Returns
    -------
    dict mapping rule number to the positions that violate it.
    """
    if isinstance(rules, str):
        try:
            rules = PRESETS[rules]
        except KeyError:
            raise ValueError(f"unknown rule preset {rules!r}; choose from {list(PRESETS)}") from None
    rules = sorted(set(int(r) for r in rules))
    bad = [r for r in rules if r not in RULE_DESCRIPTIONS]
    if bad:
        raise ValueError(f"unknown rule number(s) {bad}")

    x = np.asarray(statistic, float)
    cl = np.broadcast_to(np.asarray(center, float), x.shape)
    sd = np.broadcast_to(np.asarray(sigma, float), x.shape)
    ucl = cl + 3 * sd if ucl is None else np.broadcast_to(np.asarray(ucl, float), x.shape)
    lcl = cl - 3 * sd if lcl is None else np.broadcast_to(np.asarray(lcl, float), x.shape)

    valid = np.isfinite(x) & np.isfinite(cl)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(valid & (sd > 0), (x - cl) / sd, np.nan)

    out: dict[int, np.ndarray] = {}
    nan = ~np.isfinite(z)

    if 1 in rules:
        with np.errstate(invalid="ignore"):
            out[1] = np.flatnonzero(valid & ((x > ucl + 1e-12) | (x < lcl - 1e-12)))

    above = np.where(nan, False, z > 0)
    below = np.where(nan, False, z < 0)

    if 2 in rules:
        ra, rb = _runs(above), _runs(below)
        out[2] = np.flatnonzero((ra >= run_length) | (rb >= run_length))

    if 3 in rules or 4 in rules:
        dx = np.diff(x)
        up = np.concatenate([[False], np.isfinite(dx) & (dx > 0)])
        dn = np.concatenate([[False], np.isfinite(dx) & (dx < 0)])
        if 3 in rules:  # 6 points => 5 consecutive moves in one direction
            out[3] = np.flatnonzero((_runs(up) >= 5) | (_runs(dn) >= 5))
        if 4 in rules:  # 14 points => 13 moves, each reversing the previous
            alt = np.zeros(x.size, dtype=bool)
            for i in range(2, x.size):
                alt[i] = (up[i] and dn[i - 1]) or (dn[i] and up[i - 1])
            # a run of 12 reversals spans 13 moves = 14 points
            out[4] = np.flatnonzero(_runs(alt) >= 12)

    zz = np.where(nan, 0.0, z)
    if 5 in rules:
        out[5] = np.union1d(_k_of_m(zz > 2, 2, 3), _k_of_m(zz < -2, 2, 3))
    if 6 in rules:
        out[6] = np.union1d(_k_of_m(zz > 1, 4, 5), _k_of_m(zz < -1, 4, 5))
    if 7 in rules:
        out[7] = np.flatnonzero(_runs(~nan & (np.abs(zz) < 1)) >= 15)
    if 8 in rules:
        out[8] = np.flatnonzero(_runs(~nan & (np.abs(zz) > 1)) >= 8)

    return {r: np.asarray(v, dtype=int) for r, v in out.items()}
