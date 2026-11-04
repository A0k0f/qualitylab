"""Deming's Red Bead Experiment.

Each "willing worker" dips a paddle with 50 holes into a well-mixed bin in
which 20 % of the beads are red (defective). The count of red beads in a
worker's lot is therefore Binomial(50, 0.2): mean 10, standard deviation
√(50·0.2·0.8) ≈ 2.83. Nothing a worker does changes that distribution. Only
the *system* (here, the share of red beads the supplier delivers) does.

Deming used the experiment to show that ranking, rewarding and punishing
people for results produced by the system is futile, and that apparent
"improvement" after a warning is regression to the mean.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PADDLE = 50
RED_SHARE = 0.20
WORKERS = ["Maria", "Jamal", "Wei", "Priya", "Tom", "Sofia"]

ACTIONS = ["No action", "Praise + bonus", "Warning", "Fire and replace"]

# System changes the manager can buy in the last round: (label, red share, explanation)
SYSTEM_CHANGES = {
    "posters": dict(
        label="Motivational posters and a “Zero Defects!” campaign",
        cost=2_000, red_share=RED_SHARE, inspect=False,
        why="Slogans exhort workers to do better without giving them a better system. The red beads come from "
            "the supplier, so nothing changes (Deming's point 10: eliminate slogans and exhortations)."),
    "bonus": dict(
        label="Bonus for any worker with fewer than 8 red beads",
        cost=6_000, red_share=RED_SHARE, inspect=False,
        why="Workers cannot control which beads fall into the paddle. The bonus is paid out at random and "
            "breeds resentment (Deming's point 11: eliminate quotas and numerical goals for workers)."),
    "rehire": dict(
        label="Fire the three worst workers and hire new ones",
        cost=9_000, red_share=RED_SHARE, inspect=False,
        why="New workers use the same paddle and the same beads, so they produce the same distribution. You "
            "paid hiring costs and lost experience for nothing."),
    "inspect": dict(
        label="Add a final inspector who removes 90 % of red beads before shipping",
        cost=15_000, red_share=RED_SHARE, inspect=True,
        why="Customers receive fewer red beads, but the process makes exactly as many as before. You now "
            "pay every day to sort out defects (an appraisal cost) instead of preventing them. Deming's point 3: "
            "cease dependence on mass inspection."),
    "supplier": dict(
        label="Work with the supplier to cut red beads to 8 % of the bin",
        cost=12_000, red_share=0.08, inspect=False,
        why="This is the only option that changes the system that produces the red beads. Every worker improves "
            "at once, without anyone trying harder (Deming's point 4: work with suppliers on quality, not "
            "just price)."),
}


@dataclass
class DayResult:
    day: int
    counts: dict[str, int]

    @property
    def total(self) -> int:
        return int(sum(self.counts.values()))


def scoop(rng: np.random.Generator, red_share: float = RED_SHARE, workers=WORKERS) -> dict[str, int]:
    """One day of production: red beads in each worker's paddle."""
    return {w: int(rng.binomial(PADDLE, red_share)) for w in workers}


def control_limits(counts: list[int], n: int = PADDLE) -> dict:
    """np-chart limits estimated from the lots (as a manager would compute them)."""
    c = np.asarray(counts, float)
    pbar = c.sum() / (n * c.size)
    center = n * pbar
    sd = np.sqrt(n * pbar * (1 - pbar))
    return dict(center=center, ucl=center + 3 * sd, lcl=max(0.0, center - 3 * sd), sd=sd, pbar=pbar)


def regression_to_mean(reps: int = 100_000, seed: int = 1) -> dict:
    """What happens the day after a worker is the worst (or best), with no intervention at all."""
    rng = np.random.default_rng(seed)
    d1 = rng.binomial(PADDLE, RED_SHARE, (reps, len(WORKERS)))
    d2 = rng.binomial(PADDLE, RED_SHARE, (reps, len(WORKERS)))
    idx = np.arange(reps)
    w, b = d1.argmax(1), d1.argmin(1)
    return dict(
        worst_today=float(d1.max(1).mean()), worst_next=float(d2[idx, w].mean()),
        best_today=float(d1.min(1).mean()), best_next=float(d2[idx, b].mean()),
    )


def intervention_effects(days: list[DayResult], actions: dict[int, dict[str, str]]) -> dict:
    """Average change in red beads the day after each kind of action, from the student's own game.

    ``actions[d]`` maps worker -> action taken after day ``d``.
    """
    out: dict[str, list[int]] = {}
    by_day = {d.day: d for d in days}
    for d, acts in actions.items():
        if d not in by_day or d + 1 not in by_day:
            continue
        for w, a in acts.items():
            if a == "Fire and replace":
                continue  # a different person worked the next day
            out.setdefault(a, []).append(by_day[d + 1].counts[w] - by_day[d].counts[w])
    return {a: dict(n=len(v), mean_change=float(np.mean(v))) for a, v in out.items() if v}


def blame_index(actions: dict[int, dict[str, str]]) -> float:
    """Share of all worker-days on which the manager rewarded, warned or fired someone (0 = Deming-consistent)."""
    vals = [a for acts in actions.values() for a in acts.values()]
    if not vals:
        return 0.0
    return float(np.mean([a != "No action" for a in vals]))


def system_round(rng: np.random.Generator, change: str, days: int = 4) -> list[DayResult]:
    opt = SYSTEM_CHANGES[change]
    return [DayResult(i + 1, scoop(rng, opt["red_share"])) for i in range(days)]


def shipped_red(counts: dict[str, int], inspect: bool, rng: np.random.Generator) -> int:
    total = sum(counts.values())
    return int(rng.binomial(total, 0.1)) if inspect else total
