"""“Meet the customer's requirement”: capability as a business decision.

A machine shop turns shafts with specification 25.00 ± 0.05 mm. The process
is stable (in statistical control) but runs at 25.02 mm with σ = 0.015 mm,
so Cp = 1.11 and Cpk = 0.67. The customer requires Cpk ≥ 1.33 to keep the
contract. The player chooses improvement actions; the game computes the
resulting capability and cost, and compares with the cheapest combination
that meets the requirement.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy import stats

LSL, USL, TARGET = 24.95, 25.05, 25.00
MEAN0, SIGMA0 = 25.02, 0.015
REQUIRED_CPK = 1.33

ACTIONS = {
    "center": dict(label="Re-center the machine on 25.00 mm (offset adjustment and setup check)", cost=3_000,
                   mean=TARGET, sigma_factor=1.0),
    "training": dict(label="Train operators on a standard setup procedure (σ −10 %)", cost=4_000,
                     sigma_factor=0.90),
    "tooling": dict(label="New tooling and preventive maintenance (σ −20 %)", cost=12_000, sigma_factor=0.80),
    "machine": dict(label="Replace the machine with a new CNC lathe (σ −40 %)", cost=45_000, sigma_factor=0.60),
    "inspect": dict(label="Inspect 100 % of shafts before shipping", cost=20_000, sigma_factor=1.0,
                    inspection=True),
    "relax": dict(label="Ask the customer to accept a wider tolerance (± 0.07 mm)", cost=0, sigma_factor=1.0,
                  relax=True),
}
# The three variation-reduction options are alternative routes to the same machine variation:
# combining them gives the effect of the strongest one, not the product of all.


def cp_cpk(mean: float, sigma: float, lsl: float = LSL, usl: float = USL) -> tuple[float, float]:
    cp = (usl - lsl) / (6 * sigma)
    cpk = min(usl - mean, mean - lsl) / (3 * sigma)
    return cp, cpk


def ppm(mean: float, sigma: float, lsl: float = LSL, usl: float = USL) -> float:
    return float((stats.norm.cdf((lsl - mean) / sigma) + stats.norm.sf((usl - mean) / sigma)) * 1e6)


def outcome(chosen: list[str] | set[str]) -> dict:
    chosen = set(chosen)
    mean, sigma = MEAN0, SIGMA0
    if "center" in chosen:
        mean = TARGET
    factors = [ACTIONS[a]["sigma_factor"] for a in chosen if a in ("training", "tooling", "machine")]
    if factors:
        sigma = SIGMA0 * min(factors)
    cp, cpk = cp_cpk(mean, sigma)
    cost = sum(ACTIONS[a]["cost"] for a in chosen)
    made = ppm(mean, sigma)
    shipped = made * (0.02 if "inspect" in chosen else 1.0)
    notes = []
    if "relax" in chosen:
        notes.append("The customer declined: their assembly needs ± 0.05 mm. Specifications come from the customer, "
                     "not from what the process happens to deliver.")
    if "inspect" in chosen:
        notes.append("100 % inspection catches most bad shafts before they ship, but the process still makes them: "
                     "Cpk is unchanged, and you pay for inspection and scrap every year.")
    if len([a for a in chosen if a in ("training", "tooling", "machine")]) > 1:
        notes.append("You paid for more than one variation-reduction route; only the strongest one counts.")
    return dict(mean=mean, sigma=sigma, cp=cp, cpk=cpk, cost=cost, ppm_made=made, ppm_shipped=shipped,
                meets=cpk >= REQUIRED_CPK, notes=notes)


def cheapest_solution() -> dict:
    keys = list(ACTIONS)
    best = None
    for r in range(len(keys) + 1):
        for combo in combinations(keys, r):
            o = outcome(combo)
            if o["meets"] and (best is None or o["cost"] < best[1]["cost"]):
                best = (combo, o)
    return dict(actions=list(best[0]), **best[1])


# --- the 2×2 "in control? capable?" sorting task -------------------------------

QUADRANTS = {
    "A": dict(in_control=True, capable=True, mean=0.0, sigma=0.6, shift=None),
    "B": dict(in_control=True, capable=False, mean=0.0, sigma=1.4, shift=None),
    "C": dict(in_control=False, capable=True, mean=-0.6, sigma=0.45, shift=(14, 1.5)),
    "D": dict(in_control=False, capable=False, mean=0.3, sigma=1.1, shift=(12, 2.8)),
}


def quadrant_series(key: str, rng: np.random.Generator, n: int = 30) -> np.ndarray:
    """Values on a scale where the spec limits are ±3. Control limits are mean ± 3·sigma (from points 1-12)."""
    q = QUADRANTS[key]
    for _ in range(5000):
        x = q["mean"] + q["sigma"] * rng.standard_normal(n)
        if q["shift"]:
            s, size = q["shift"]
            x[s:] += size * q["sigma"]
        lim_hi, lim_lo = q["mean"] + 3 * q["sigma"], q["mean"] - 3 * q["sigma"]
        beyond = (x > lim_hi) | (x < lim_lo)
        out_spec = (np.abs(x) > 3).mean()
        if q["in_control"] and beyond.any():
            continue
        if not q["in_control"] and beyond.sum() < 2:
            continue
        if q["capable"] and out_spec > 0:
            continue
        if not q["capable"] and out_spec < 0.05:
            continue
        return x
    raise RuntimeError("could not generate quadrant series")  # pragma: no cover
