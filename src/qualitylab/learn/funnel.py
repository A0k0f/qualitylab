"""Deming's funnel experiment, recast as a filling machine.

A machine aimed at ``aim`` fills a bottle with ``aim + e``, where ``e`` is
natural variation (Normal(0, σ)). After each fill the operator may move the
aim. Deming's four rules:

1. Never adjust. Spread = σ (the best possible for this system).
2. Move the aim by minus the last error, measured from the last aim
   (``aim -= x - T``). Spread = σ√2 (variance doubles).
3. Set the aim to the mirror image of the last result about the target
   (``aim = T - (x - T)``). Oscillates with ever-growing swings.
4. Set the aim at the last result (``aim = x``). A random walk that wanders
   off.

Rules 2–4 are all *tampering*: reacting to common-cause variation.
"""
from __future__ import annotations

import numpy as np

TARGET = 12.00
SIGMA = 0.10
RULES = {
    1: "Leave the machine alone",
    2: "After each bottle, move the aim by the opposite of its error (from where it was)",
    3: "After each bottle, set the aim to the target minus the bottle's error",
    4: "After each bottle, set the aim to the weight of that bottle",
}


def run_rule(rule: int, noise: np.ndarray, target: float = TARGET) -> dict:
    aims, fills = [], []
    aim = target
    for e in noise:
        x = aim + e
        aims.append(aim)
        fills.append(x)
        if rule == 1:
            pass
        elif rule == 2:
            aim = aim - (x - target)
        elif rule == 3:
            aim = target - (x - target)
        elif rule == 4:
            aim = x
        else:
            raise ValueError("rule must be 1-4")
    f = np.asarray(fills)
    return dict(aims=np.asarray(aims), fills=f, sd=float(np.sqrt(np.mean((f - target) ** 2))))


def replay_manual(adjustments: list[float], noise: np.ndarray, target: float = TARGET) -> dict:
    """Fills the player produced: adjustment i is applied after fill i."""
    aim = target
    aims, fills = [], []
    for i, e in enumerate(noise[: len(adjustments) + 1]):
        x = aim + e
        aims.append(aim)
        fills.append(x)
        if i < len(adjustments):
            aim += adjustments[i]
    f = np.asarray(fills)
    return dict(aims=np.asarray(aims), fills=f, sd=float(np.sqrt(np.mean((f - target) ** 2))))


def tampering_index(adjustments: list[float], fills: np.ndarray, target: float = TARGET) -> dict:
    """How the player reacted to each fill's error.

    ``slope`` is the regression slope of adjustment on the last error:
    0 = left the process alone (rule 1), −1 = fully compensated each error
    (rule 2). ``share_adjusted`` is the share of fills after which the aim was
    moved at all.
    """
    a = np.asarray(adjustments, float)
    err = np.asarray(fills[: len(a)], float) - target
    moved = np.abs(a) > 1e-9
    if a.size < 2 or np.allclose(err, err.mean()):
        slope = 0.0
    else:
        slope = float(np.polyfit(err, a, 1)[0])
    return dict(slope=slope, share_adjusted=float(moved.mean()) if a.size else 0.0,
                mean_abs_adjustment=float(np.abs(a).mean()) if a.size else 0.0)


def theoretical_sd(rule: int, n: int, sigma: float = SIGMA) -> float:
    """Root-mean-square deviation from target over n fills."""
    if rule == 1:
        return sigma
    if rule == 2:
        # first fill has variance σ², later fills 2σ²
        return sigma * np.sqrt((1 + 2 * (n - 1)) / n)
    # rules 3 and 4: deviation at fill k has variance k·σ²
    return sigma * np.sqrt((n + 1) / 2)
