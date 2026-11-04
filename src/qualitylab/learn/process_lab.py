"""Process Lab: open-ended experiments on a process that the student defines.

Nothing here is a fixed scenario. The student sets:

* the **process**: what is measured, its target and specification limits, how much it
  varies from unit to unit (common-cause variation), where it is actually centered,
  how many units are measured per sample, how many samples are taken, how many units
  are made between samples, and the costs that matter;
* the **changes** that happen to it, and when: a sudden shift in the average, a gradual
  drift, an increase in variation, or a one-off outlier (or nothing at all);
* the **monitoring**: Shewhart chart (X̄-R, X̄-S or I-MR, picked from the sample size),
  EWMA or CUSUM; which run rules; whether limits are estimated from a baseline period
  or set from the known target and variation; and whether people react to signals
  (investigate, find the cause and remove it).

``run`` draws new random data from those settings, runs the chart with the validated
QualityLab chart functions, and measures what happened: when each change was caught,
false alarms, out-of-spec output, and cost. ``replicate`` repeats an experiment many
times so that a single lucky or unlucky run is not mistaken for the truth.

Modelling choices (stated to students in the app):

* Units in a sample are independent normal draws around the current process mean.
* During the baseline period the chart is being set up, so nobody reacts to signals.
* After the baseline, every signal triggers an investigation. If something has really
  changed, the investigation finds it and the process returns to how it was before the
  change from the next sample on, and the chart restarts (run rules, EWMA and CUSUM forget
  the old data). If nothing has changed, the investigation costs money and finds nothing
  (a false alarm).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np
from scipy import stats

from .. import charts
from .. import rules as rules_mod
from ..result import ChartResult

CHANGE_KINDS = {
    "shift": "Sudden shift in the average",
    "drift": "Gradual drift in the average",
    "spread": "More variation (spread)",
    "outlier": "One-off unusual sample",
}
CHART_TYPES = {
    "shewhart": "Shewhart chart (X̄-R, X̄-S or I-MR)",
    "ewma": "EWMA chart",
    "cusum": "CUSUM chart",
}
RULE_SETS = {
    "limits": "Only points beyond the limits",
    "western_electric": "Western Electric rules (limits, runs of 8, 2-of-3, 4-of-5)",
    "nelson": "All eight Nelson rules",
}


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------

@dataclass
class Process:
    name: str = "My process"
    unit: str = "units"
    target: float = 100.0
    lsl: float | None = 97.0
    usl: float | None = 103.0
    sigma: float = 1.0          # unit-to-unit (common-cause) standard deviation
    mean: float | None = None   # where the process is actually centered (None = on target)
    n: int = 5                  # units measured per sample
    samples: int = 60           # samples in the experiment
    baseline: int = 20          # first samples used to set up the chart
    units_per_sample: int = 500  # units produced between two samples
    cost_check: float = 2.0     # cost to measure one unit
    cost_investigation: float = 200.0  # cost of one investigation
    cost_defect: float = 25.0   # cost of one out-of-spec unit reaching a customer

    @property
    def mu0(self) -> float:
        return self.target if self.mean is None else float(self.mean)

    def problems(self) -> list[str]:
        p = []
        if not self.sigma > 0:
            p.append("Variation (standard deviation) must be greater than 0.")
        if self.lsl is None and self.usl is None:
            p.append("Give at least one specification limit.")
        if self.lsl is not None and self.usl is not None and self.lsl >= self.usl:
            p.append("The lower specification limit must be below the upper one.")
        if not 1 <= self.n <= 25:
            p.append("Units per sample must be between 1 and 25.")
        if not 20 <= self.samples <= 500:
            p.append("Number of samples must be between 20 and 500.")
        if not 10 <= self.baseline <= self.samples - 5:
            p.append("The baseline needs at least 10 samples and must leave at least 5 for monitoring.")
        for k in ("units_per_sample", "cost_check", "cost_investigation", "cost_defect"):
            if getattr(self, k) < 0:
                p.append("Volumes and costs cannot be negative.")
                break
        return p


@dataclass
class Change:
    kind: str = "shift"   # shift | drift | spread | outlier
    at: int = 40          # sample number (1-based) where it starts
    size: float = 1.0     # shift/outlier: units; drift: units per sample; spread: multiplier of σ

    def problems(self, proc: Process) -> list[str]:
        p = []
        if self.kind not in CHANGE_KINDS:
            p.append(f"Unknown change type {self.kind!r}.")
        if not 1 <= self.at <= proc.samples:
            p.append(f"A change must start between sample 1 and {proc.samples}.")
        if self.kind == "spread" and not self.size > 0:
            p.append("A change in spread is a multiplier and must be greater than 0 (e.g. 1.5).")
        return p

    def describe(self, proc: Process) -> str:
        u = proc.unit
        if self.kind == "shift":
            return f"the average shifts by {self.size:+g} {u} ({self.size / proc.sigma:+.2g}σ) at sample {self.at}"
        if self.kind == "drift":
            return f"the average drifts by {self.size:+g} {u} per sample from sample {self.at}"
        if self.kind == "spread":
            return f"variation becomes {self.size:g}× larger at sample {self.at}"
        return f"one unusual sample, off by {self.size:+g} {u}, at sample {self.at}"


@dataclass
class Monitor:
    chart: str = "shewhart"         # shewhart | ewma | cusum
    rules: str = "western_electric"  # for Shewhart charts
    limits_from: str = "baseline"   # baseline | known (target and σ as entered)
    react: bool = True
    lam: float = 0.2                # EWMA weight
    L_ewma: float = 2.962           # Lucas & Saccucci (1990): in-control ARL ≈ 500 with λ = 0.2
    k: float = 0.5                  # CUSUM reference value (in σ of the plotted statistic)
    h: float = 5.0                  # CUSUM decision interval

    def problems(self) -> list[str]:
        p = []
        if self.chart not in CHART_TYPES:
            p.append(f"Unknown chart {self.chart!r}.")
        if self.rules not in RULE_SETS:
            p.append(f"Unknown rule set {self.rules!r}.")
        if self.limits_from not in ("baseline", "known"):
            p.append("Limits must come from the baseline or from the known values.")
        if not 0 < self.lam <= 1:
            p.append("EWMA weight λ must be between 0 and 1.")
        if not self.h > 0 or self.k < 0:
            p.append("CUSUM settings must be positive.")
        return p


@dataclass
class Experiment:
    process: Process = field(default_factory=Process)
    changes: list[Change] = field(default_factory=list)
    monitor: Monitor = field(default_factory=Monitor)

    def problems(self) -> list[str]:
        p = self.process.problems() + self.monitor.problems()
        for c in self.changes:
            p += c.problems(self.process)
        return p

    def to_dict(self) -> dict:
        return dict(process=asdict(self.process), changes=[asdict(c) for c in self.changes],
                    monitor=asdict(self.monitor))

    @classmethod
    def from_dict(cls, d: dict) -> Experiment:
        return cls(Process(**d["process"]), [Change(**c) for c in d.get("changes", [])], Monitor(**d["monitor"]))


def diff(a: dict | None, b: dict) -> list[str]:
    """Names of the settings that differ between two experiment dicts (for research logs)."""
    if a is None:
        return []
    out = []
    for part in ("process", "monitor"):
        for k, v in b[part].items():
            if a[part].get(k) != v:
                out.append(f"{part}.{k}")
    if a.get("changes") != b.get("changes"):
        out.append("changes")
    return out


# ---------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------

def _paths(exp: Experiment, fixed: dict[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """True mean and σ of every sample, and which changes are active, given fix times."""
    P = exp.process
    m = P.samples
    t = np.arange(m)
    mu = np.full(m, P.mu0, float)
    sd = np.full(m, P.sigma, float)
    active = np.zeros((len(exp.changes), m), bool)
    for j, c in enumerate(exp.changes):
        start = c.at - 1
        end = m if c.kind != "outlier" else start + 1
        if j in fixed:
            end = min(end, fixed[j] + 1)
        on = (t >= start) & (t < end)
        active[j] = on
        if c.kind == "shift" or c.kind == "outlier":
            mu[on] += c.size
        elif c.kind == "drift":
            mu[on] += c.size * (t[on] - start + 1)
        elif c.kind == "spread":
            sd[on] *= c.size
    return mu, sd, active


def _segments(m: int, resets: list[int]) -> list[tuple[int, int]]:
    """[start, end) pieces of the run; a new piece starts after every fix (charts restart there)."""
    cuts = [0] + [r + 1 for r in sorted(resets) if r + 1 < m] + [m]
    return [(a, b) for a, b in zip(cuts[:-1], cuts[1:]) if b > a]


def _stitch(name, kind, pieces, params, phase1, labels) -> ChartResult:
    cat = {k: np.concatenate([getattr(p, k) for p, _ in pieces]) for k in ("statistic", "center", "ucl", "lcl", "sigma")}
    res = ChartResult(name, cat["statistic"], cat["center"], cat["ucl"], cat["lcl"], cat["sigma"], labels, phase1,
                      params=params, kind=kind)
    viol: dict[int, list] = {}
    for p, off in pieces:
        for rule, idx in p.violations.items():
            viol.setdefault(rule, []).extend((np.asarray(idx, int) + off).tolist())
    res.violations = {k: np.array(sorted(set(v)), int) for k, v in viol.items() if v}
    if kind == "cusum":
        res.extra["C_minus"] = np.concatenate([p.extra["C_minus"] for p, _ in pieces])
    return res


def _chart(exp: Experiment, X: np.ndarray, resets: list[int] | None = None):
    """Run the chosen chart. Limits come from the baseline (or the known values) and never change; after
    a fix the chart restarts (run rules, EWMA and CUSUM forget what came before), as they would in practice.
    Returns (main chart, dispersion chart or None, signal positions)."""
    P, M = exp.process, exp.monitor
    m, n = X.shape
    phase1 = np.arange(m) < P.baseline
    known = M.limits_from == "known"
    run_length = 8 if M.rules == "western_electric" else 9
    segs = _segments(m, resets or [])
    mu_k, sd_k = (P.target, P.sigma) if known else (None, None)

    # Shewhart pair: limits from the baseline (or known values)
    if n == 1:
        base, disp = charts.imr(X[:, 0], phase1=phase1, rules=M.rules, run_length=run_length, mu=mu_k, sigma=sd_k)
        se_mean = float(base.params["sigma"])
    else:
        f = charts.xbar_r if n <= 10 else charts.xbar_s
        base, disp = f(X, phase1=phase1, rules=M.rules, run_length=run_length, mu=mu_k, sigma=sd_k)
        se_mean = float(base.params["sigma"]) / math.sqrt(n)
    mu0 = float(base.params["mu"])
    means = X.mean(axis=1)

    pieces = []
    for a, b in segs:
        if M.chart == "shewhart":
            v = rules_mod.evaluate(base.statistic[a:b], base.center[a:b], base.sigma[a:b], base.ucl[a:b],
                                   base.lcl[a:b], rules=M.rules, run_length=run_length)
            piece = ChartResult(base.name, base.statistic[a:b], base.center[a:b], base.ucl[a:b], base.lcl[a:b],
                                base.sigma[a:b], base.labels[a:b], phase1[a:b], violations=v)
        elif M.chart == "ewma":
            piece = charts.ewma(means[a:b], lam=M.lam, L=M.L_ewma, mu=mu0, sigma=se_mean)
        else:
            piece = charts.cusum(means[a:b], k=M.k, h=M.h, mu=mu0, sigma=se_mean)
        pieces.append((piece, a))
    kind = {"shewhart": "shewhart", "ewma": "ewma", "cusum": "cusum"}[M.chart]
    name = base.name if M.chart == "shewhart" else M.chart.upper()
    params = dict(base.params, mu=mu0, sigma=float(base.params["sigma"]), se_mean=se_mean)
    if M.chart == "cusum":
        params.update(H=M.h * se_mean, K=M.k * se_mean)
    main = _stitch(name, kind, pieces, params, phase1, base.labels)
    sig = set(main.out_of_control.tolist())
    if M.chart == "shewhart":
        sig |= set(disp.out_of_control.tolist())
    else:
        disp = None
    return main, disp, np.array(sorted(sig), int)


def _oos(mu: np.ndarray, sd: np.ndarray, lsl, usl) -> np.ndarray:
    p = np.zeros_like(mu)
    if lsl is not None:
        p += stats.norm.cdf((lsl - mu) / sd)
    if usl is not None:
        p += stats.norm.sf((usl - mu) / sd)
    return p


def run(exp: Experiment, seed: int, *, keep_data: bool = True) -> dict:
    """One experiment with fresh random data. All randomness comes from ``seed``."""
    probs = exp.problems()
    if probs:
        raise ValueError(" ".join(probs))
    P, M = exp.process, exp.monitor
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal((P.samples, P.n))
    fixed: dict[int, int] = {}
    for _ in range(len(exp.changes) + 2):
        mu, sd, active = _paths(exp, fixed)
        X = mu[:, None] + sd[:, None] * Z
        main, disp, signals = _chart(exp, X, list(fixed.values()))
        if not M.react:
            break
        new = False
        for s in signals:
            if s < P.baseline:
                continue
            hit = [j for j in range(len(exp.changes)) if active[j, s] and j not in fixed]
            if hit:
                for j in hit:
                    fixed[j] = int(s)
                new = True
                break  # recompute from here: everything after s changes
        if not new:
            break

    # --- outcome measures -------------------------------------------------------------
    m = P.samples
    t = np.arange(m)
    monitoring = t >= P.baseline
    any_active = active.any(axis=0) if len(exp.changes) else np.zeros(m, bool)
    sig_mask = np.zeros(m, bool)
    sig_mask[signals] = True
    quiet = monitoring & ~any_active
    false_alarms = int((sig_mask & quiet).sum())
    investigations = int((sig_mask & monitoring).sum()) if M.react else 0

    change_out = []
    for j, c in enumerate(exp.changes):
        start = c.at - 1
        later = signals[signals >= start]
        if c.kind == "outlier":
            later = later[later == start]
        first = int(later[0]) if later.size else None
        change_out.append(dict(kind=c.kind, at=c.at, size=c.size, detected=first is not None,
                               signal_at=None if first is None else first + 1,
                               delay=None if first is None else first - start + 1,
                               in_baseline=start < P.baseline, fixed_at=None if j not in fixed else fixed[j] + 1))

    p_oos = _oos(mu, sd, P.lsl, P.usl)
    defects = p_oos * P.units_per_sample
    produced = P.units_per_sample * m
    costs = dict(checking=P.cost_check * P.n * m,
                 investigations=P.cost_investigation * investigations,
                 defects=P.cost_defect * float(defects.sum()))
    costs["total"] = sum(costs.values())

    base = X[: P.baseline]
    cap = _capability(base, P)
    out = dict(
        seed=int(seed), signals=[int(s) + 1 for s in signals], fixed={j: s + 1 for j, s in fixed.items()},
        changes=change_out, false_alarms=false_alarms, quiet_samples=int(quiet.sum()),
        investigations=investigations, oos_units=float(defects.sum()), oos_share=float(defects.sum() / produced),
        costs=costs, capability=cap, chart_name=main.name, sigma_hat=float(main.params.get("sigma", np.nan)),
    )
    if keep_data:
        out.update(X=X, mu=mu, sd=sd, active=active, main=main, disp=disp, p_oos=p_oos)
    return out


def _capability(base: np.ndarray, P: Process) -> dict:
    """Capability from the baseline samples (estimated) and from the settings (true)."""
    x = base.ravel()
    s = x.std(ddof=1)
    mean = x.mean()
    sides = [v for v in ((P.usl - mean) if P.usl is not None else None,
                         (mean - P.lsl) if P.lsl is not None else None) if v is not None]
    est_cpk = min(sides) / (3 * s)
    true_sides = [v for v in ((P.usl - P.mu0) if P.usl is not None else None,
                              (P.mu0 - P.lsl) if P.lsl is not None else None) if v is not None]
    true_cpk = min(true_sides) / (3 * P.sigma)
    both = P.lsl is not None and P.usl is not None
    return dict(cp=float((P.usl - P.lsl) / (6 * s)) if both else None, cpk=float(est_cpk),
                true_cp=float((P.usl - P.lsl) / (6 * P.sigma)) if both else None, true_cpk=float(true_cpk),
                baseline_mean=float(mean), baseline_sd=float(s))


def replicate(exp: Experiment, reps: int = 200, seed: int = 0) -> dict:
    """Repeat the experiment ``reps`` times with new random data."""
    ss = np.random.SeedSequence(seed)
    rows = [run(exp, int(s.generate_state(1)[0]), keep_data=False) for s in ss.spawn(reps)]
    out = dict(reps=reps, seed=int(seed),
               false_alarms_per_100=float(100 * sum(r["false_alarms"] for r in rows)
                                          / max(1, sum(r["quiet_samples"] for r in rows))),
               runs_with_false_alarm=float(np.mean([r["false_alarms"] > 0 for r in rows])),
               oos_share=float(np.mean([r["oos_share"] for r in rows])),
               cost=float(np.mean([r["costs"]["total"] for r in rows])),
               cost_p10=float(np.percentile([r["costs"]["total"] for r in rows], 10)),
               cost_p90=float(np.percentile([r["costs"]["total"] for r in rows], 90)),
               changes=[])
    for j in range(len(exp.changes)):
        d = [r["changes"][j] for r in rows]
        delays = np.array([x["delay"] for x in d if x["detected"]], float)
        out["changes"].append(dict(detected=float(np.mean([x["detected"] for x in d])),
                                   delay_median=float(np.median(delays)) if delays.size else None,
                                   delay_mean=float(delays.mean()) if delays.size else None,
                                   delays=delays.astype(int).tolist()))
    return out


# ---------------------------------------------------------------------------
# helpers for the app
# ---------------------------------------------------------------------------

def sigma_note(size: float, sigma: float, n: int) -> str:
    """How big a change is in the units a chart 'sees'."""
    z = size / sigma
    return f"{z:+.2g}σ for one unit, {z * math.sqrt(n):+.2g}σ for a sample average of {n}"


def shewhart_name(n: int) -> str:
    return "I-MR" if n == 1 else ("X̄-R" if n <= 10 else "X̄-S")


def theoretical_shewhart(exp: Experiment) -> dict:
    """Textbook expectations for a Shewhart chart with known limits and rule 1 only (for comparison)."""
    P = exp.process
    p0 = 2 * stats.norm.sf(3)
    out = dict(false_alarm_per_100=100 * p0, arl0=1 / p0, shifts=[])
    for c in exp.changes:
        if c.kind == "shift":
            d = c.size / P.sigma * math.sqrt(P.n)
            p1 = stats.norm.sf(3 - d) + stats.norm.cdf(-3 - d)
            out["shifts"].append(dict(at=c.at, arl1=1 / p1))
    return out
