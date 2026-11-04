"""“Signal or noise?”: a signal-detection game for control-chart judgment.

Each round shows an individuals chart of 25 daily values with control limits
set from earlier, normal operation (mean μ, standard deviation σ known).
Half the rounds contain a real change (special cause); half are pure
common-cause noise. The player decides whether to investigate.

Rounds are generated in four difficulty categories, with the same mix in
every phase, so that performance before and after the lesson is comparable:

``noise_plain``     noise that never comes near the limits
``noise_tempting``  noise with one point between 2.3σ and 2.95σ (looks alarming, is not)
``signal_obvious``  a change that puts at least one point beyond 3σ
``signal_subtle``   a change no single point reveals, caught only by the run rules

Noise rounds never violate the taught run rules and every signal round does,
so applying the rules is a perfect strategy. Performance is summarized with
signal-detection measures: hit rate, false-alarm rate and d′.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats

from ..rules import evaluate

TAUGHT_RULES = (1, 2, 3, 5, 6)  # with run_length = 8 (Western Electric) and the 6-point trend
RUN_LENGTH = 8
RULE_TEXT = {
    1: "A point beyond a control limit",
    2: "8 points in a row on the same side of the center line",
    3: "6 points in a row steadily increasing or decreasing",
    5: "2 of 3 points in a row beyond 2σ, on the same side",
    6: "4 of 5 points in a row beyond 1σ, on the same side",
}

CONTEXTS = [
    dict(name="Average call wait", unit="min", mu=4.0, sigma=0.4, worse="up",
         story="A bank's call center tracks the average time customers wait, every day."),
    dict(name="Bottle fill weight", unit="g", mu=500.0, sigma=1.5, worse="both",
         story="A bottling line weighs a sample of bottles every shift.", period="shift"),
    dict(name="Invoice processing time", unit="h", mu=26.0, sigma=2.5, worse="up",
         story="An accounts-payable team logs the average time to approve an invoice, every day."),
    dict(name="On-time delivery rate", unit="%", mu=94.0, sigma=1.2, worse="down",
         story="A distribution center reports the share of orders delivered on time, every day."),
    dict(name="Hotel check-in time", unit="min", mu=6.0, sigma=0.7, worse="up",
         story="A hotel front desk tracks the average check-in time, every day."),
    dict(name="Pizza delivery time", unit="min", mu=32.0, sigma=2.0, worse="up",
         story="A pizza chain tracks average delivery time at one store, every day."),
    dict(name="Shaft diameter", unit="mm", mu=25.00, sigma=0.01, worse="both",
         story="A machine shop measures one shaft per hour.", period="hour"),
    dict(name="Website checkout errors", unit="per 1,000", mu=12.0, sigma=1.5, worse="up",
         story="An online store tracks checkout errors per 1,000 sessions, every day."),
]

CATEGORIES = ("noise_plain", "noise_tempting", "signal_obvious", "signal_subtle")
PHASE_MIX = ("noise_plain", "noise_plain", "noise_tempting", "noise_tempting",
             "signal_obvious", "signal_subtle", "signal_subtle", "signal_subtle")
N_POINTS = 25

# money at stake per round (shown to players)
COST_INVESTIGATE = 300
COST_MISS = 2_000


@dataclass
class Round:
    round_id: str
    phase: str
    category: str
    is_signal: bool
    kind: str                 # none / shift / trend / outlier
    start: int | None         # 0-based index where the change begins
    context: dict
    values: list[float]
    rules_fired: dict[int, list[int]]

    @property
    def z(self) -> np.ndarray:
        c = self.context
        return (np.asarray(self.values) - c["mu"]) / c["sigma"]

    def to_log(self) -> dict:
        d = asdict(self)
        d["context"] = self.context["name"]
        return d


def _rules(z: np.ndarray) -> dict[int, np.ndarray]:
    v = evaluate(z, 0.0, 1.0, rules=TAUGHT_RULES, run_length=RUN_LENGTH)
    return {r: idx for r, idx in v.items() if idx.size}


def _direction(ctx: dict, rng: np.random.Generator) -> int:
    if ctx["worse"] == "up":
        return 1
    if ctx["worse"] == "down":
        return -1
    return int(rng.choice([-1, 1]))


def _make(category: str, ctx: dict, rng: np.random.Generator) -> tuple[np.ndarray, str, int | None] | None:
    z = rng.standard_normal(N_POINTS)
    sgn = _direction(ctx, rng)
    if category == "noise_plain":
        if np.abs(z).max() > 2.2 or _rules(z):
            return None
        return z, "none", None
    if category == "noise_tempting":
        m = np.abs(z).max()
        if not (2.3 < m < 2.95) or _rules(z) or np.argmax(np.abs(z)) < 8:
            return None
        return z, "none", None
    kind = rng.choice(["shift", "trend", "outlier"] if category == "signal_obvious" else ["shift", "trend"])
    if kind == "outlier":
        start = int(rng.integers(12, N_POINTS - 1))
        z[start] = sgn * rng.uniform(3.6, 4.5)
    elif kind == "shift":
        start = int(rng.integers(9, 17))
        size = rng.uniform(1.6, 2.4) if category == "signal_obvious" else rng.uniform(1.1, 1.6)
        z[start:] += sgn * size
    else:
        start = int(rng.integers(8, 15))
        slope = rng.uniform(0.25, 0.4) if category == "signal_obvious" else rng.uniform(0.12, 0.2)
        z[start:] += sgn * slope * np.arange(1, N_POINTS - start + 1)
    fired = _rules(z)
    if not fired:
        return None
    # no false signal before the change starts (keeps the ground truth unambiguous)
    if any((idx < start).any() for idx in fired.values()):
        return None
    beyond = np.abs(z).max() > 3
    if category == "signal_obvious" and not beyond:
        return None
    if category == "signal_subtle" and beyond:
        return None
    return z, str(kind), start


def make_round(category: str, rng: np.random.Generator, *, phase: str, round_id: str,
               context: dict | None = None) -> Round:
    ctx = context or CONTEXTS[int(rng.integers(len(CONTEXTS)))]
    for _ in range(20_000):
        r = _make(category, ctx, rng)
        if r is not None:
            z, kind, start = r
            vals = ctx["mu"] + ctx["sigma"] * z
            return Round(round_id, phase, category, category.startswith("signal"), kind, start, ctx,
                         [float(v) for v in vals], {k: [int(i) for i in v] for k, v in _rules(z).items()})
    raise RuntimeError(f"could not generate a {category} round")  # pragma: no cover


def make_phase(phase: str, seed: int) -> list[Round]:
    """Eight rounds with the standard difficulty mix, in random order, each with a different context."""
    rng = np.random.default_rng(seed)
    cats = list(PHASE_MIX)
    rng.shuffle(cats)
    ctx_order = rng.permutation(len(CONTEXTS))
    return [make_round(c, rng, phase=phase, round_id=f"{phase}{i + 1}", context=CONTEXTS[ctx_order[i]])
            for i, c in enumerate(cats)]


def payoff(is_signal: bool, investigate: bool) -> int:
    if investigate:
        return (COST_MISS - COST_INVESTIGATE) if is_signal else -COST_INVESTIGATE
    return -COST_MISS if is_signal else 0


def outcome_label(is_signal: bool, investigate: bool) -> str:
    return {(True, True): "hit", (True, False): "miss", (False, True): "false alarm",
            (False, False): "correct pass"}[(is_signal, investigate)]


def dprime(hits: int, n_signal: int, false_alarms: int, n_noise: int) -> dict:
    """Signal-detection sensitivity with the log-linear correction (Hautus, 1995)."""
    h = (hits + 0.5) / (n_signal + 1)
    f = (false_alarms + 0.5) / (n_noise + 1)
    d = stats.norm.ppf(h) - stats.norm.ppf(f)
    c = -0.5 * (stats.norm.ppf(h) + stats.norm.ppf(f))
    return dict(hit_rate=hits / n_signal if n_signal else np.nan,
                false_alarm_rate=false_alarms / n_noise if n_noise else np.nan,
                dprime=float(d), criterion=float(c))


def explain(r: Round) -> str:
    """Plain-language feedback after the player decides."""
    c = r.context
    if not r.is_signal:
        msg = "Nothing changed: this was common-cause variation only."
        if r.category == "noise_tempting":
            msg += (" One point came close to a limit, which is expected now and then: about 1 point in 20 falls "
                    "beyond 2σ by chance. A single point inside the limits, with no pattern, is not a signal.")
        return msg
    what = {"shift": "the average shifted", "trend": "a gradual drift began", "outlier": "a one-off disruption hit"}
    worse = {"up": "up", "down": "down"}.get(c["worse"], "")
    first = min(min(v) for v in r.rules_fired.values())
    rules = "; ".join(f"{RULE_TEXT[k]} (first at day {min(v) + 1})" for k, v in sorted(r.rules_fired.items()))
    msg = f"A real change: {what[r.kind]} on day {r.start + 1}{(' (' + worse + ')') if worse else ''}. "
    msg += f"The chart first signalled on day {first + 1}. Rules that caught it: {rules}."
    return msg
