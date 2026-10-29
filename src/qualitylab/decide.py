"""Turn simulations into decisions.

* :func:`optimize` searches hundreds of monitoring and inspection plans and
  returns the cheapest one that meets your constraints, plus the simplest plan
  that is nearly as cheap.
* :func:`sensitivity` asks whether the answer survives if your cost and
  frequency estimates are off.
* :func:`best_aim` finds the process setting (e.g. fill target) that balances
  overfill against out-of-spec risk.
* :func:`compare_investments` estimates the return on process improvements
  (better equipment, preventive maintenance, training).
* :func:`calibrate` estimates process inputs from historical data.
* :func:`explain` writes the recommendation in plain language.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .simulate import Evaluation, FailureMode, Policy, Process, _giveaway, _pdef, evaluate

SIMPLICITY = {"none": 0, "spec": 1, "shewhart": 2, "adjust": 2, "ewma": 3, "cusum": 3}


# ---------------------------------------------------------------------------
# candidate plans
# ---------------------------------------------------------------------------

def candidate_policies(process: Process, current: Policy | None = None, *, thorough: bool = False) -> list[Policy]:
    """A grid of sensible monitoring plans for this process."""
    hpd = process.hours_per_day
    base = [0.5, 1, 2, 4, 8, hpd, 5 * hpd] + ([0.25, 3, 6, 12] if thorough else [])
    intervals = sorted({float(x) for x in base if x <= 5 * hpd})
    if process.kind == "measurement":
        sizes = [1, 2, 3, 5, 8]
        charts = [("spec", {}), ("shewhart", {"L": 3.0}), ("shewhart", {"L": 2.5}),
                  ("ewma", {"lam": 0.2, "L": 2.86}), ("cusum", {"k": 0.5, "h": 4.0})]
        if thorough:
            sizes += [4, 10]
            charts += [("ewma", {"lam": 0.1, "L": 2.7}), ("cusum", {"k": 0.5, "h": 5.0})]
    else:
        p0 = process.defect_rate
        by_rate = {int(max(5, round(m / p0))) for m in (0.25, 0.5, 1, 2, 5, 10)}
        sizes = sorted(by_rate | {10, 20, 50, 100, 200, 500})
        charts = [("spec", {}), ("shewhart", {"L": 3.0}), ("ewma", {"lam": 0.2, "L": 2.86}),
                  ("cusum", {"k": 0.5, "h": 4.0})]
        if thorough:
            charts += [("shewhart", {"L": 2.5}), ("cusum", {"k": 0.5, "h": 5.0}), ("ewma", {"lam": 0.1, "L": 2.7})]
    out = [Policy("none")]
    for h in intervals:
        cap = process.units_per_hour * h
        for n in sizes:
            if n > cap:
                continue
            for c, kw in charts:
                if c == "spec" and process.kind == "pass_fail" and n * process.defect_rate > 0.7:
                    continue  # "act on any defect" with this many units would alarm most of the time
                out.append(Policy(c, n=n, every_hours=h, **kw))
    if current is not None:
        cur = Policy(**{**current.__dict__, "final": "none"})
        if cur.monitoring_key() not in {p.monitoring_key() for p in out}:
            out.append(cur)
    return out


def final_options(process: Process, current: Policy | None = None) -> list[dict]:
    opts = [dict(final="none"), dict(final="screen")]
    lot_units = process.units_per_hour * process.lot_length
    for n, c in ((32, 0), (50, 1), (80, 2), (125, 3), (200, 5), (315, 7)):
        if n < lot_units:
            opts.append(dict(final="lots", lot_n=n, lot_c=c))
    if current is not None and current.final == "lots":
        d = dict(final="lots", lot_n=current.lot_n, lot_c=current.lot_c)
        if d not in opts:
            opts.append(d)
    return opts


def _with_final(p: Policy, f: dict) -> Policy:
    d = {**p.__dict__, "final": "none", "lot_n": 50, "lot_c": 1, "label": ""}
    d.update(f)
    return Policy(**d)


# ---------------------------------------------------------------------------
# optimization
# ---------------------------------------------------------------------------

@dataclass
class Decision:
    process: Process
    current: Evaluation
    best: Evaluation
    simplest: Evaluation
    no_checks: Evaluation
    table: pd.DataFrame
    evaluations: list[Evaluation] = field(repr=False)
    constraints: dict = field(default_factory=dict)
    feasible: bool = True

    @property
    def savings(self) -> np.ndarray:
        return self.current.total - self.simplest.total

    def top(self, k: int = 10) -> pd.DataFrame:
        return self.table.head(k)


def _table(process: Process, evs: list[Evaluation]) -> pd.DataFrame:
    rows = []
    for i, e in enumerate(evs):
        s = e.summary()
        s["_i"] = i
        s["plan"] = e.policy.describe(process)
        s["simplicity"] = SIMPLICITY[e.policy.check] + (1 if e.policy.final != "none" else 0)
        rows.append(s)
    return pd.DataFrame(rows)


def optimize(
    process: Process,
    current: Policy,
    *,
    max_escape_ppm: float | None = None,
    max_false_alarms_per_week: float | None = None,
    reps: int = 400,
    years: float = 0.25,
    seed: int = 0,
    tolerance: float = 0.05,
    thorough: bool = False,
    progress: Callable[[float], None] | None = None,
) -> Decision:
    """Search monitoring × final-inspection plans for the lowest expected annual cost.

    ``tolerance``: the *simplest* plan within this fraction of the best cost is
    also reported. A plan that operators understand is often worth a few
    percent.
    """
    process.validate()
    mon = candidate_policies(process, current, thorough=thorough)
    finals = final_options(process, current)
    pols = [_with_final(p, f) for p in mon for f in finals]
    pols.append(current)
    # evaluate in chunks by interval so we can report progress
    by_int: dict[float, list[int]] = {}
    for i, p in enumerate(pols):
        by_int.setdefault(p.every_hours if p.check != "none" else 1.0, []).append(i)
    evs: list[Evaluation | None] = [None] * len(pols)
    done = 0
    for _, idx in sorted(by_int.items()):
        res = evaluate(process, [pols[i] for i in idx], reps=reps, years=years, seed=seed)
        for i, r in zip(idx, res):
            evs[i] = r
        done += len(idx)
        if progress:
            progress(done / len(pols))
    evs_ok: list[Evaluation] = evs  # type: ignore[assignment]
    tab = _table(process, evs_ok)
    ok = np.ones(len(tab), bool)
    if max_escape_ppm is not None:
        ok &= tab["escapes_ppm"].to_numpy() <= max_escape_ppm
    if max_false_alarms_per_week is not None:
        ok &= tab["false_alarms_per_week"].to_numpy() <= max_false_alarms_per_week
    tab["meets_constraints"] = ok
    feasible = bool(ok.any())
    pool = tab[ok] if feasible else tab
    best_i = int(pool.sort_values("annual_cost").iloc[0]["_i"])
    near = pool[pool["annual_cost"] <= evs_ok[best_i].mean_cost * (1 + tolerance)]
    simp_i = int(near.sort_values(["simplicity", "units_tested_per_year", "annual_cost"]).iloc[0]["_i"])
    none_i = next(i for i, p in enumerate(pols) if p.check == "none" and p.final == "none")
    tab = tab.drop_duplicates(subset=["policy"]).sort_values("annual_cost").reset_index(drop=True)
    return Decision(process, evs_ok[-1], evs_ok[best_i], evs_ok[simp_i], evs_ok[none_i], tab, evs_ok,
                    dict(max_escape_ppm=max_escape_ppm, max_false_alarms_per_week=max_false_alarms_per_week),
                    feasible)


# ---------------------------------------------------------------------------
# robustness
# ---------------------------------------------------------------------------

def _scale_costs(p: Process, attr: str, f: float) -> Process:
    q = p.copy()
    setattr(q.costs, attr, getattr(q.costs, attr) * f)
    return q


def _scale_freq(p: Process, f: float) -> Process:
    q = p.copy()
    for fm in q.failure_modes:
        fm.every_hours = fm.every_hours / f
    return q


def _scale_size(p: Process, f: float) -> Process:
    q = p.copy()
    for fm in q.failure_modes:
        fm.shift *= f
        fm.drift_per_hour *= f
        fm.sigma_factor = 1 + (fm.sigma_factor - 1) * f
        fm.rate_factor = 1 + (fm.rate_factor - 1) * f
    return q


SENSITIVITY_FACTORS: dict[str, Callable[[Process, float], Process]] = {
    "Cost of a defect reaching a customer": lambda p, f: _scale_costs(p, "escape", f),
    "How often problems occur": _scale_freq,
    "How big problems are": _scale_size,
    "Cost of a false alarm": lambda p, f: _scale_costs(p, "false_alarm", f),
    "Cost of testing a unit": lambda p, f: _scale_costs(p, "per_unit_tested", f),
}


def sensitivity(decision: Decision, *, low: float = 0.5, high: float = 1.5, reps: int = 300,
                years: float = 0.25, seed: int = 11, extra: int = 4, tolerance: float = 0.10) -> pd.DataFrame:
    """Re-run the key plans with each uncertain input at ×low and ×high.

    Returns one row per input: savings of the recommended plan over the current
    one at each end, and its *regret* — how much more it costs than the best of
    the plans compared (current, recommended, cheapest, no checks and the next
    ``extra`` runners-up). ``recommended_still_best_*`` is True when the regret
    is within ``tolerance`` (10 %) of the best cost.
    """
    d = decision
    contenders = [d.current.policy, d.simplest.policy, d.best.policy, d.no_checks.policy]
    for _, r in d.table.head(extra + 3).iterrows():
        contenders.append(d.evaluations[int(r["_i"])].policy)
    uniq: list[Policy] = []
    for p in contenders:
        if all(p.short() != q.short() for q in uniq):
            uniq.append(p)
    rows = []
    for name, fn in SENSITIVITY_FACTORS.items():
        row = {"input": name}
        for tag, f in (("low", low), ("high", high)):
            evs = evaluate(fn(d.process, f), uniq, reps=reps, years=years, seed=seed)
            costs = {e.policy.short(): e.mean_cost for e in evs}
            rec = costs[d.simplest.policy.short()]
            row[f"savings_{tag}"] = costs[d.current.policy.short()] - rec
            winner = min(costs, key=costs.get)
            regret = rec - costs[winner]
            row[f"regret_{tag}"] = regret
            row[f"regret_pct_{tag}"] = regret / max(abs(costs[winner]), 1e-9)
            row[f"recommended_still_best_{tag}"] = regret <= tolerance * abs(costs[winner]) + 1e-9
            row[f"best_plan_{tag}"] = winner
        rows.append(row)
    out = pd.DataFrame(rows)
    out["swing"] = (out["savings_high"] - out["savings_low"]).abs()
    return out.sort_values("swing", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# process aim
# ---------------------------------------------------------------------------

def best_aim(process: Process, *, points: int = 401) -> pd.DataFrame:
    """Expected cost per unit (in-control) as a function of the process mean setting.

    Balances giveaway (overfill above target) against the cost of units outside
    spec reaching customers. Returns a table with the cost curve; the minimum is
    the recommended aim. Measurement processes only.
    """
    process.validate()
    if process.kind != "measurement":
        raise ValueError("process aim applies to measurement processes")
    s = process.sigma
    lo = (process.lsl if process.lsl is not None else process.mean - 6 * s) - 1 * s
    hi = (process.usl if process.usl is not None else process.mean + 6 * s) + 1 * s
    grid = np.linspace(lo, hi, points)
    pdef = _pdef(grid, s, process.lsl, process.usl)
    give = _giveaway(grid, s, process.target) if process.costs.giveaway > 0 else np.zeros_like(grid)
    c = process.costs
    per_unit = pdef * c.escape + give * c.giveaway
    return pd.DataFrame({"aim": grid, "defect_rate": pdef, "giveaway_per_unit": give,
                         "cost_per_unit": per_unit, "annual_cost": per_unit * process.units_per_year})


def aim_recommendation(process: Process) -> dict:
    """The cost-minimizing aim versus today's, in annual dollars (in-control, before inspection)."""
    tab = best_aim(process)
    i = int(tab["cost_per_unit"].idxmin())
    cur = float(np.interp(process.mean, tab["aim"], tab["annual_cost"]))
    best = float(tab.loc[i, "annual_cost"])
    return dict(best_aim=float(tab.loc[i, "aim"]), current_aim=float(process.mean),
                annual_cost_now=cur, annual_cost_best=best, annual_savings=cur - best,
                defect_rate_now=float(np.interp(process.mean, tab["aim"], tab["defect_rate"])),
                defect_rate_best=float(tab.loc[i, "defect_rate"]), table=tab)


# ---------------------------------------------------------------------------
# investments
# ---------------------------------------------------------------------------

@dataclass
class Investment:
    """A process improvement and what it changes.

    ``variation_factor`` multiplies σ (measurement); ``defect_rate_factor``
    multiplies the baseline defect rate (pass/fail); ``frequency_factor``
    multiplies how often problems occur (0.5 = half as often);
    ``size_factor`` scales how big problems are; ``notice_factor`` scales how
    long problems go unnoticed without monitoring.
    """

    name: str
    annual_cost: float
    variation_factor: float = 1.0
    defect_rate_factor: float = 1.0
    frequency_factor: float = 1.0
    size_factor: float = 1.0
    notice_factor: float = 1.0

    def apply(self, p: Process) -> Process:
        q = p.copy()
        if q.kind == "measurement":
            q.sigma = q.sigma * self.variation_factor
        else:
            q.defect_rate = min(0.999, q.defect_rate * self.defect_rate_factor)
        if self.frequency_factor != 1:
            q = _scale_freq(q, self.frequency_factor)
        if self.size_factor != 1:
            q = _scale_size(q, self.size_factor)
        if q.notice_after_hours is not None:
            q.notice_after_hours *= self.notice_factor
        return q


def compare_investments(decision: Decision, investments: list[Investment], *, reps: int = 300,
                        years: float = 0.25, seed: int = 21) -> pd.DataFrame:
    """Net annual benefit of each investment, re-choosing the best of the top plans for each."""
    d = decision
    plans = [d.simplest.policy, d.best.policy, d.current.policy, d.no_checks.policy]
    for _, r in d.table.head(12).iterrows():
        plans.append(d.evaluations[int(r["_i"])].policy)
    uniq: list[Policy] = []
    for p in plans:
        if all(p.short() != q.short() for q in uniq):
            uniq.append(p)
    base = min(evaluate(d.process, uniq, reps=reps, years=years, seed=seed), key=lambda e: e.mean_cost)
    rows = [dict(investment="(none: best plan as-is)", plan=base.policy.short(), operating_cost=base.mean_cost,
                 investment_cost=0.0, total=base.mean_cost, net_benefit=0.0, payback_months=np.nan)]
    for inv in investments:
        evs = evaluate(inv.apply(d.process), uniq, reps=reps, years=years, seed=seed)
        b = min(evs, key=lambda e: e.mean_cost)
        total = b.mean_cost + inv.annual_cost
        gross = base.mean_cost - b.mean_cost
        rows.append(dict(investment=inv.name, plan=b.policy.short(), operating_cost=b.mean_cost,
                         investment_cost=inv.annual_cost, total=total, net_benefit=base.mean_cost - total,
                         payback_months=(12 * inv.annual_cost / gross) if gross > 0 else np.inf))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# calibration from data
# ---------------------------------------------------------------------------

def calibrate(values=None, *, defectives=None, sizes=None, hours_between: float | None = None) -> dict:
    """Estimate process inputs from history.

    Measurement data (``values``: 1-D individual values, or 2-D rows of
    subgroups): mean, short-term σ (moving range or within-subgroup), and the
    number of distinct out-of-control episodes on an individuals/X̄ chart.
    Pass/fail data (``defectives`` and ``sizes``): baseline defect rate.
    With ``hours_between`` (time between observations) the episode count is
    converted into a rough "a problem about every N hours" estimate.
    """
    from .charts import imr, p_chart, xbar_s

    out: dict = {}
    if values is not None:
        arr = values.to_numpy(dtype=float) if isinstance(values, (pd.DataFrame, pd.Series)) else np.asarray(values, float)
        if arr.ndim == 2 and arr.shape[1] > 1:
            xr, _ = xbar_s(arr)
            out.update(mean=float(np.nanmean(arr)), sigma=float(xr.params["sigma"]))
            chart = xr
        else:
            x = arr.ravel()
            x = x[np.isfinite(x)]
            ir, _ = imr(x)
            out.update(mean=float(x.mean()), sigma=float(ir.params["sigma"]))
            chart = ir
        flags = np.zeros(len(chart.statistic), bool)
        flags[chart.out_of_control] = True
        episodes = int(np.sum(flags[1:] & ~flags[:-1]) + flags[0])
        out.update(points=len(chart.statistic), episodes=episodes)
    elif defectives is not None:
        d = np.asarray(defectives, float)
        n = np.broadcast_to(np.asarray(sizes, float), d.shape)
        pc = p_chart(d, n)
        flags = np.zeros(len(d), bool)
        flags[pc.out_of_control] = True
        episodes = int(np.sum(flags[1:] & ~flags[:-1]) + flags[0])
        clean = ~flags
        rate = d[clean].sum() / n[clean].sum() if clean.any() else d.sum() / n.sum()
        out.update(defect_rate=float(rate), points=len(d), episodes=episodes)
    else:
        raise ValueError("give measurement values, or defectives and sizes")
    if hours_between and out["episodes"] > 0:
        out["problem_every_hours"] = out["points"] * hours_between / out["episodes"]
    return out


# ---------------------------------------------------------------------------
# plain-language summary
# ---------------------------------------------------------------------------

def _money(x: float) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e6:
        return f"{sign}${x / 1e6:,.2f}M"
    if x >= 1e4:
        return f"{sign}${x / 1e3:,.0f}k"
    if x < 10 and x != int(x):
        return f"{sign}${x:,.2f}"
    return f"{sign}${x:,.0f}"


def explain(decision: Decision) -> list[str]:
    d = decision
    cur, rec = d.current.summary(), d.simplest.summary()
    sav = d.savings
    lo, hi = np.percentile(sav, [10, 90])
    msgs = []
    if not d.feasible:
        msgs.append("No plan met all your constraints. The recommendation below is the cheapest plan overall; "
                    "consider relaxing a constraint or investing in the process itself.")
    if d.simplest.policy.short() == d.current.policy.short() or sav.mean() <= 0.01 * max(1.0, cur["annual_cost"]):
        msgs.append(f"**Your current approach is already close to the best plan found.** Expected cost: "
                    f"{_money(cur['annual_cost'])} a year.")
    else:
        msgs.append(f"**Recommended:** {d.simplest.policy.describe(d.process)}.")
        msgs.append(f"**Expected saving: {_money(sav.mean())} a year** compared with today "
                    f"({_money(cur['annual_cost'])} → {_money(rec['annual_cost'])}). In 8 out of 10 simulated "
                    f"years the saving was between {_money(lo)} and {_money(hi)}.")
    msgs.append(
        f"Problems are fixed after **{rec['hours_to_fix']:.1f} h** on average (today: {cur['hours_to_fix']:.1f} h). "
        f"Defects reaching customers: **{rec['escapes_ppm']:,.0f} per million** (today: {cur['escapes_ppm']:,.0f}). "
        f"False alarms: **{rec['false_alarms_per_week']:.1f} per week** (today: {cur['false_alarms_per_week']:.1f}).")
    if rec["hours_to_fix"] > 1.2 * cur["hours_to_fix"] and d.simplest.policy.final != "none":
        msgs.append("Note the trade-off: this plan finds process problems *more slowly* than today. It saves money "
                    "mainly by sorting bad output before it ships, not by catching problems sooner.")
    if d.best.policy.short() != d.simplest.policy.short():
        gap = d.simplest.mean_cost - d.best.mean_cost
        msgs.append(f"The absolute cheapest plan found ({d.best.policy.short()}) would save another "
                    f"{_money(gap)} a year but is harder to run; the recommendation trades that for simplicity.")
    if d.current.policy.check == "adjust":
        msgs.append("Re-aiming the process after every check (without a chart) reacts to random noise and "
                    "*adds* variation. This is the classic tampering trap.")
    nc = d.no_checks.summary()
    msgs.append(f"For reference, doing no routine checks at all would cost about {_money(nc['annual_cost'])} a year.")
    return msgs


def cost_breakdown(*evals: Evaluation, labels: list[str] | None = None) -> pd.DataFrame:
    """Expected annual cost by category, one row per evaluation."""
    labels = labels or [e.policy.short() for e in evals]
    rows = [{k: float(np.mean(v)) for k, v in e.parts.items()} for e in evals]
    return pd.DataFrame(rows, index=labels)


__all__ = ["Decision", "Investment", "FailureMode", "aim_recommendation", "best_aim", "calibrate",
           "candidate_policies", "compare_investments", "cost_breakdown", "explain", "optimize", "sensitivity"]
