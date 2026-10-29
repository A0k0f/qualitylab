"""What-if simulation: a process, the problems that hit it, and the policies used to catch them.

The model
---------
A process makes ``units_per_hour`` units. Each unit is either a *measurement*
(fill volume, diameter: defective when outside the spec limits) or *pass/fail*
(an order picked wrong, an invoice with an error).

From time to time a **problem** (an assignable cause, a "failure mode")
occurs: a clogged nozzle, tool wear, a new temp worker. A problem moves the
process (mean shift, slow drift, more variation, or a higher error rate) and
stays until it is found and fixed, either by the **monitoring policy** or,
failing that, because someone notices it anyway after ``notice_after_hours``
(a customer complaint, an end-of-week report).

A **policy** says how the process is watched:

* ``check``: ``"none"``; ``"spec"`` (check *n* units, act if any is out of spec);
  ``"shewhart"``, ``"ewma"``, ``"cusum"`` (plot the sample on a control chart and
  act when it signals); or ``"adjust"`` (re-aim the machine after every check
  by the sample's distance from target, i.e. *tampering*)
* ``n`` units every ``every_hours`` hours
* ``final``: what happens before shipping: ``"none"``; ``"screen"`` (100 %
  inspection that catches a share ``inspection_effectiveness`` of defects); or
  ``"lots"`` (sample ``lot_n`` units from each lot and reject the lot when more
  than ``lot_c`` are defective; rejected lots are 100 % screened)

Every check, false alarm, repair, scrapped unit, escaped defect and unit of
overfill (giveaway) has a cost. The simulation runs many years of operation
and reports the expected annual cost of each policy and its spread.

Assumptions (stated so users can judge them): one problem at a time; a fixed
problem is fixed immediately; the chart's in-control mean and σ are known
(i.e. Phase I has been done); defect counts use expected values within each
time step (this removes noise without changing the averages).
"""
from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field, fields

import numpy as np
from scipy import special

CHECKS = ("none", "spec", "shewhart", "ewma", "cusum", "adjust")
FINALS = ("none", "screen", "lots")
_CODE = {c: i for i, c in enumerate(CHECKS)}


# ---------------------------------------------------------------------------
# scenario description
# ---------------------------------------------------------------------------

@dataclass
class FailureMode:
    """Something that goes wrong.

    ``every_hours``: average operating hours between occurrences.
    Measurement processes: ``shift`` moves the mean (in measurement units),
    ``drift_per_hour`` keeps moving it after onset, ``sigma_factor`` multiplies
    the variation. Pass/fail processes: ``rate_factor`` multiplies the defect
    rate and ``drift_per_hour`` adds to that multiplier every hour.
    """

    name: str
    every_hours: float
    shift: float = 0.0
    drift_per_hour: float = 0.0
    sigma_factor: float = 1.0
    rate_factor: float = 1.0


@dataclass
class Costs:
    escape: float = 0.0             # per defective unit that reaches the customer
    internal: float = 0.0           # per defective unit caught in house (scrap / rework)
    per_unit_tested: float = 0.0    # per unit measured or tested (checks and lot samples)
    per_check: float = 0.0          # fixed cost per check (walking over, recording)
    false_alarm: float = 0.0        # per investigation that finds nothing
    repair: float = 0.0             # per real problem found and fixed
    per_unit_screened: float = 0.0  # per unit in 100 % inspection
    giveaway: float = 0.0           # measurement only: per measurement unit above target, per unit made


@dataclass
class Process:
    name: str
    kind: str                       # "measurement" or "pass_fail"
    units_per_hour: float
    hours_per_day: float = 16.0
    days_per_year: float = 250.0
    failure_modes: list[FailureMode] = field(default_factory=list)
    notice_after_hours: float | None = None   # None = never noticed without monitoring
    costs: Costs = field(default_factory=Costs)
    inspection_effectiveness: float = 0.9     # share of defects caught by 100 % inspection
    lot_hours: float | None = None            # a lot = output of this many hours (default: one day)
    description: str = ""
    # measurement processes
    unit_label: str = ""
    target: float | None = None
    mean: float | None = None
    sigma: float | None = None
    lsl: float | None = None
    usl: float | None = None
    # pass/fail processes
    defect_rate: float | None = None

    # -- derived -------------------------------------------------------
    @property
    def hours_per_year(self) -> float:
        return self.hours_per_day * self.days_per_year

    @property
    def units_per_year(self) -> float:
        return self.units_per_hour * self.hours_per_year

    @property
    def lot_length(self) -> float:
        return self.lot_hours or self.hours_per_day

    def validate(self) -> None:
        if self.kind not in ("measurement", "pass_fail"):
            raise ValueError("kind must be 'measurement' or 'pass_fail'")
        if self.units_per_hour <= 0 or self.hours_per_day <= 0 or self.days_per_year <= 0:
            raise ValueError("production volume and operating time must be positive")
        if self.kind == "measurement":
            if self.mean is None or self.sigma is None or self.sigma <= 0:
                raise ValueError("a measurement process needs a mean and a positive sigma")
            if self.lsl is None and self.usl is None:
                raise ValueError("give at least one specification limit")
            if self.lsl is not None and self.usl is not None and self.lsl >= self.usl:
                raise ValueError("LSL must be below USL")
            if self.target is None:
                self.target = (self.lsl + self.usl) / 2 if (self.lsl is not None and self.usl is not None) else self.mean
        else:
            if self.defect_rate is None or not 0 < self.defect_rate < 1:
                raise ValueError("a pass/fail process needs a defect rate between 0 and 1")
        for fm in self.failure_modes:
            if fm.every_hours <= 0:
                raise ValueError(f"failure mode {fm.name!r}: 'every_hours' must be positive")
            if fm.sigma_factor <= 0 or fm.rate_factor <= 0:
                raise ValueError(f"failure mode {fm.name!r}: factors must be positive")
        if not 0 <= self.inspection_effectiveness <= 1:
            raise ValueError("inspection effectiveness must be between 0 and 1")

    # -- serialization ---------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> Process:
        d = copy.deepcopy(d)
        d["failure_modes"] = [FailureMode(**fm) for fm in d.get("failure_modes", [])]
        d["costs"] = Costs(**d.get("costs", {}))
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    @classmethod
    def from_json(cls, s: str) -> Process:
        return cls.from_dict(json.loads(s))

    def copy(self, **changes) -> Process:
        p = copy.deepcopy(self)
        for k, v in changes.items():
            setattr(p, k, v)
        return p


@dataclass
class Policy:
    check: str = "none"
    n: int = 1
    every_hours: float = 1.0
    L: float = 3.0
    lam: float = 0.2
    k: float = 0.5
    h: float = 5.0
    final: str = "none"
    lot_n: int = 50
    lot_c: int = 1
    label: str = ""

    def __post_init__(self):
        if self.check not in CHECKS:
            raise ValueError(f"check must be one of {CHECKS}")
        if self.final not in FINALS:
            raise ValueError(f"final must be one of {FINALS}")
        if self.check != "none" and (self.n < 1 or self.every_hours <= 0):
            raise ValueError("checks need n >= 1 and a positive interval")
        if self.final == "lots" and not 0 <= self.lot_c < self.lot_n:
            raise ValueError("lot plan needs 0 <= c < n")

    def monitoring_key(self) -> tuple:
        """Identifies the part of the policy that changes process dynamics."""
        if self.check == "none":
            return ("none",)
        base = (self.check, int(self.n), float(self.every_hours))
        if self.check == "shewhart":
            return base + (self.L,)
        if self.check == "ewma":
            return base + (self.lam, self.L)
        if self.check == "cusum":
            return base + (self.k, self.h)
        return base

    def describe(self, process: Process | None = None) -> str:
        unit = "unit" if self.n == 1 else "units"
        every = _fmt_hours(self.every_hours)
        if self.check == "none":
            s = "No routine checks"
        elif self.check == "spec":
            s = f"Check {self.n} {unit} every {every}; stop and investigate if any is out of spec"
        elif self.check == "shewhart":
            s = (f"Check {self.n} {unit} every {every}; plot on a control chart "
                 f"({self.L:g}σ limits) and investigate when a point falls outside")
        elif self.check == "ewma":
            s = (f"Check {self.n} {unit} every {every}; track an EWMA chart (λ={self.lam:g}) "
                 "and investigate when it signals")
        elif self.check == "cusum":
            s = f"Check {self.n} {unit} every {every}; track a CUSUM chart (h={self.h:g}) and investigate when it signals"
        else:
            s = f"Check {self.n} {unit} every {every} and re-aim the process after every check (no chart)"
        if self.final == "screen":
            s += "; inspect 100 % of output before shipping"
        elif self.final == "lots":
            lot = "each lot" if process is None else f"each {_fmt_hours(process.lot_length)} lot"
            rule = "any is defective" if self.lot_c == 0 else f"more than {self.lot_c} are defective"
            s += f"; sample {self.lot_n} units from {lot} and reject it if {rule} (rejected lots are 100 % inspected)"
        return s

    def short(self) -> str:
        if self.check == "none":
            m = "No checks"
        else:
            name = {"spec": "Spec check", "shewhart": f"Shewhart {self.L:g}σ", "ewma": f"EWMA λ={self.lam:g}",
                    "cusum": f"CUSUM h={self.h:g}", "adjust": "Re-aim every check"}[self.check]
            if self.check == "ewma" and self.L != 2.86:
                name += f" L={self.L:g}"
            if self.check == "cusum" and self.k != 0.5:
                name += f" k={self.k:g}"
            m = f"{name}, n={self.n} every {_fmt_hours(self.every_hours)}"
        f = {"none": "", "screen": " + 100% inspection", "lots": f" + lot sampling ({self.lot_n},{self.lot_c})"}[self.final]
        return m + f


def _fmt_hours(h: float) -> str:
    if h < 1:
        return f"{h * 60:g} min"
    if h == 1:
        return "hour"
    return f"{h:g} h"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _pdef(mu, s, lsl, usl):
    out = np.zeros(np.broadcast(mu, s).shape)
    if lsl is not None:
        out = out + special.ndtr((lsl - mu) / s)
    if usl is not None:
        out = out + special.ndtr((mu - usl) / s)
    return np.minimum(out, 1.0)


def _giveaway(mu, s, target):
    """E[(X - target)+] for X ~ N(mu, s)."""
    d = (mu - target) / s
    return s * np.exp(-0.5 * d * d) / np.sqrt(2 * np.pi) + (mu - target) * special.ndtr(d)


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------

def _simulate_group(process: Process, policies: list[Policy], *, reps: int, years: float,
                    seed: int, substeps: int = 1, record: bool = False) -> dict:
    """Simulate policies that share one check interval, all replications at once.

    Returns arrays of shape (P, R) with totals over the horizon, plus per-lot
    defects of shape (P, R, lots).
    """
    pr = process
    meas = pr.kind == "measurement"
    P, R = len(policies), reps
    every = policies[0].every_hours if policies[0].check != "none" else 1.0
    dt = every / substeps
    horizon = pr.hours_per_year * years
    n_epochs = max(1, int(round(horizon / dt)))
    rng = np.random.default_rng(seed)

    col = lambda vals, dtype=float: np.asarray(vals, dtype=dtype)[:, None]  # noqa: E731
    code = col([_CODE[p.check] for p in policies], int)
    nn = col([max(1, p.n) for p in policies])
    L = col([p.L for p in policies])
    lam = col([p.lam for p in policies])
    kk = col([p.k for p in policies])
    hh = col([p.h for p in policies])
    is_none = code == _CODE["none"]

    fms = pr.failure_modes
    if fms:
        rates = np.array([1.0 / f.every_hours for f in fms])
        cum = np.cumsum(rates / rates.sum())
        p_occ = 1 - np.exp(-rates.sum() * dt)
        f_shift = np.array([f.shift for f in fms])
        f_drift = np.array([f.drift_per_hour for f in fms])
        f_sig = np.array([f.sigma_factor for f in fms])
        f_rate = np.array([f.rate_factor for f in fms])
        has_drift = bool(np.any(f_drift != 0))
    else:
        p_occ = 0.0
        has_drift = False
    notice = np.inf if pr.notice_after_hours is None else float(pr.notice_after_hours)
    uph = pr.units_per_hour
    lot_len = pr.lot_length
    n_lots = int(np.ceil(horizon / lot_len))

    if meas:
        mu0, s0 = float(pr.mean), float(pr.sigma)
        lsl, usl, T = pr.lsl, pr.usl, float(pr.target)
        want_give = pr.costs.giveaway > 0
    else:
        p0 = float(pr.defect_rate)
        sd0 = np.sqrt(nn * p0 * (1 - p0))
        n_int = nn.astype(np.int64)

    shape = (P, R)
    active = np.zeros(shape, bool)
    mode = np.zeros(shape, int)
    onset = np.zeros(shape)
    offset = np.zeros(shape)
    w = np.zeros(shape)
    cp = np.zeros(shape)
    cm = np.zeros(shape)
    tsr = np.zeros(shape)
    acc = {k: np.zeros(shape) for k in ("checks", "false_alarms", "chart_fixes", "ext_fixes", "problems",
                                         "ooc_hours", "defects", "giveaway", "fix_delay")}
    lot_def = np.zeros((P, R, n_lots))
    rec = {"t": [], "level": [], "active": [], "signal": [], "false": [], "ext": [], "check": []} if record else None

    adj_rows = np.flatnonzero(code[:, 0] == _CODE["adjust"]) if meas else np.array([], int)
    spec_rows = code[:, 0] == _CODE["spec"]
    if meas:
        p_ic0 = float(_pdef(np.float64(mu0), s0, lsl, usl))
        g_ic0 = float(_giveaway(np.float64(mu0), s0, T)) if want_give else 0.0

    def level_sel(t, sel):
        """Process level of the disturbed elements ``sel`` (boolean mask) at times t[sel]."""
        m = mode[sel]
        age = np.maximum(t[sel] - onset[sel], 0.0)
        if meas:
            mu = mu0 + offset[sel] + f_shift[m] + f_drift[m] * age
            return mu, s0 * f_sig[m]
        return np.minimum(1.0, p0 * (f_rate[m] + f_drift[m] * age)), None

    def rates_sel(t, sel):
        a, b = level_sel(t, sel)
        if meas:
            return _pdef(a, b, lsl, usl), (_giveaway(a, b, T) if want_give else 0.0)
        return a, 0.0

    def full_level(t):
        """Process level of every element at scalar time t (cheap: no special functions)."""
        tt = np.full(shape, t)
        if meas:
            mu = mu0 + offset
            sd = np.full(shape, s0)
            if active.any():
                mu_a, s_a = level_sel(tt, active)
                mu[active], sd[active] = mu_a, s_a
            return mu, sd
        pp = np.full(shape, p0)
        if active.any():
            pp[active] = level_sel(tt, active)[0]
        return pp, None

    for e in range(n_epochs):
        t0 = e * dt
        t1 = t0 + dt
        # --- new problems (common random numbers across policies) ---
        if fms:
            u = rng.random(R)
            occ = (~active) & (u < p_occ)[None, :]
            if occ.any():
                uo, um = rng.random(R), rng.random(R)
                onset = np.where(occ, (t0 + uo * dt)[None, :], onset)
                mode = np.where(occ, np.searchsorted(cum, um)[None, :], mode)
                active = active | occ
                acc["problems"] += occ
        # --- output during the step: in-control part ---
        if meas:
            p_ic = np.full(shape, p_ic0)
            g_ic = np.full(shape, g_ic0) if want_give else 0.0
            if adj_rows.size:
                mu_adj = mu0 + offset[adj_rows]
                p_ic[adj_rows] = _pdef(mu_adj, s0, lsl, usl)
                if want_give:
                    g_ic[adj_rows] = _giveaway(mu_adj, s0, T)
        else:
            p_ic, g_ic = p0, 0.0
        d_e = uph * dt * p_ic + np.zeros(shape)
        give_e = uph * dt * g_ic if (meas and want_give) else None
        endfix = onset + notice
        # --- problem part (only for disturbed elements) ---
        if active.any():
            a = np.where(active, np.maximum(t0, onset), t1)
            b = np.maximum(a, np.where(active, np.minimum(t1, endfix), t1))
            dur = b - a
            sel = active
            if has_drift:  # Simpson's rule over the problem segment
                pa, ga = rates_sel(a, sel)
                pm, gm = rates_sel((a + b) / 2, sel)
                pb, gb = rates_sel(b, sel)
                p_ooc = (pa + 4 * pm + pb) / 6
                g_ooc = (ga + 4 * gm + gb) / 6 if give_e is not None else 0.0
            else:
                p_ooc, g_ooc = rates_sel(a, sel)
            ds = dur[sel]
            pic_sel = p_ic[sel] if np.ndim(p_ic) else p_ic
            d_e[sel] += uph * ds * (p_ooc - pic_sel)
            if give_e is not None:
                give_e[sel] += uph * ds * (g_ooc - g_ic[sel])
            acc["ooc_hours"] += dur
        acc["defects"] += d_e
        if give_e is not None:
            acc["giveaway"] += give_e
        lot_def[:, :, min(n_lots - 1, int(((t0 + t1) / 2) // lot_len))] += d_e

        if record:  # state during this step, before any fix
            act_rec = active.copy()
            lvl_rec = full_level(t1)[0].copy()

        # --- problems noticed anyway (customer complaint, report) ---
        ext = active & (endfix <= t1)
        if ext.any():
            acc["ext_fixes"] += ext
            acc["fix_delay"] += np.where(ext, notice, 0.0)
            active = active & ~ext
            for arr in (w, cp, cm, tsr):
                arr[ext] = 0.0

        # --- the check ---
        signal = false = None
        is_check = (e + 1) % substeps == 0
        if is_check:
            acc["checks"] += ~is_none
            lvl, s_now = full_level(t1)
            if meas:
                z_noise = rng.standard_normal(R)[None, :]
                xbar = lvl + s_now / np.sqrt(nn) * z_noise
                z = (xbar - mu0) / (s0 / np.sqrt(nn))
                spec_act = np.zeros(shape, bool)
                if spec_rows.any():
                    pd_now = np.full(shape, p_ic0)
                    sa = active & spec_rows[:, None]
                    if sa.any():
                        pd_now[sa] = _pdef(lvl[sa], s_now[sa], lsl, usl)
                    spec_act = rng.random(shape) < 1 - (1 - pd_now) ** nn
                shew = np.abs(z) > L
            else:
                cnt = rng.binomial(n_int, lvl)
                z = (cnt - nn * p0) / sd0
                spec_act = cnt > 0
                shew = z > L
            tsr += 1
            w = lam * z + (1 - lam) * w
            lim = L * np.sqrt(lam / (2 - lam) * (1 - (1 - lam) ** (2 * tsr)))
            ew = (np.abs(w) > lim) if meas else (w > lim)
            cp = np.maximum(0.0, z - kk + cp)
            cm = np.maximum(0.0, -z - kk + cm)
            cu = ((cp > hh) | (cm > hh)) if meas else (cp > hh)
            signal = np.select(
                [code == _CODE["spec"], code == _CODE["shewhart"], code == _CODE["ewma"], code == _CODE["cusum"]],
                [spec_act, shew, ew, cu], default=False)
            true = signal & active
            false = signal & ~active
            acc["chart_fixes"] += true
            acc["fix_delay"] += np.where(true, t1 - onset, 0.0)
            acc["false_alarms"] += false
            active = active & ~true
            for arr in (w, cp, cm, tsr):
                arr[signal] = 0.0
            if adj_rows.size:
                offset[adj_rows] -= (xbar[adj_rows] - mu0)
        if record:
            rec["t"].append(t1)
            rec["level"].append(lvl_rec)
            rec["active"].append(act_rec)
            rec["check"].append(is_check)
            rec["signal"].append(np.zeros(shape, bool) if signal is None else signal.copy())
            rec["false"].append(np.zeros(shape, bool) if false is None else false.copy())
            rec["ext"].append(ext.copy())

    out = dict(acc)
    out["units_tested"] = acc["checks"] * nn
    out["lot_defects"] = lot_def
    out["years"] = years
    out["horizon_hours"] = n_epochs * dt
    if record:
        out["record"] = {k: np.array(v) for k, v in rec.items()}
    return out


# ---------------------------------------------------------------------------
# accounting
# ---------------------------------------------------------------------------

def _lot_accept_prob(f, n, c):
    """P(at most c defectives in a sample of n | defect fraction f), binomial."""
    f = np.clip(f, 0, 1)
    tot = np.zeros_like(f)
    for i in range(c + 1):
        tot = tot + special.comb(n, i) * f**i * (1 - f) ** (n - i)
    return np.minimum(tot, 1.0)


def _account(process: Process, policy: Policy, sim: dict, row: int) -> dict:
    """Annual cost breakdown (per replication) for one policy."""
    c = process.costs
    yrs = sim["years"]
    units = process.units_per_hour * sim["horizon_hours"]
    D = sim["defects"][row]
    lots = sim["lot_defects"][row]  # (R, n_lots)
    eff = process.inspection_effectiveness
    lot_units = process.units_per_hour * process.lot_length

    screen_cost = np.zeros_like(D)
    lot_test_units = np.zeros_like(D)
    if policy.final == "none":
        escapes, internal = D, np.zeros_like(D)
    elif policy.final == "screen":
        escapes, internal = (1 - eff) * D, eff * D
        screen_cost = np.full_like(D, units * c.per_unit_screened)
    else:
        f = lots / lot_units
        pa = _lot_accept_prob(f, policy.lot_n, policy.lot_c)
        rej = 1 - pa
        escapes = (pa * lots + (1 - eff) * rej * lots).sum(axis=1)
        internal = (eff * rej * lots).sum(axis=1)
        screen_cost = (rej * max(0.0, lot_units - policy.lot_n)).sum(axis=1) * c.per_unit_screened
        lot_test_units = np.full_like(D, lots.shape[1] * policy.lot_n)

    parts = {
        "Routine checks": sim["checks"][row] * c.per_check + (sim["units_tested"][row] + lot_test_units) * c.per_unit_tested,
        "False alarms": sim["false_alarms"][row] * c.false_alarm,
        "Fixing real problems": (sim["chart_fixes"][row] + sim["ext_fixes"][row]) * c.repair,
        "100% inspection": screen_cost,
        "Scrap / rework": internal * c.internal,
        "Defects reaching customers": escapes * c.escape,
        "Giveaway (overfill)": sim["giveaway"][row] * c.giveaway,
    }
    parts = {k: v / yrs for k, v in parts.items()}
    total = sum(parts.values())
    fixes = sim["chart_fixes"][row] + sim["ext_fixes"][row]
    weeks = process.days_per_year * yrs / 5  # operating weeks of 5 days
    return dict(
        total=total, parts=parts,
        escapes_ppm=escapes / units * 1e6,
        escapes_per_year=escapes / yrs,
        defects_made_per_year=D / yrs,
        false_alarms_per_week=sim["false_alarms"][row] / weeks,
        problems_per_year=sim["problems"][row] / yrs,
        caught_by_checks=np.divide(sim["chart_fixes"][row], np.maximum(fixes, 1)),
        hours_to_fix=np.divide(sim["fix_delay"][row], np.maximum(fixes, 1)),
        share_time_with_problem=sim["ooc_hours"][row] / sim["horizon_hours"],
        units_tested_per_year=(sim["units_tested"][row] + lot_test_units) / yrs,
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

@dataclass
class Evaluation:
    """Results for one policy: per-replication arrays and summaries."""

    policy: Policy
    total: np.ndarray
    parts: dict
    metrics: dict

    @property
    def mean_cost(self) -> float:
        return float(self.total.mean())

    def summary(self) -> dict:
        m = {k: float(np.mean(v)) for k, v in self.metrics.items()}
        return dict(
            policy=self.policy.short(),
            annual_cost=self.mean_cost,
            cost_p10=float(np.percentile(self.total, 10)),
            cost_p90=float(np.percentile(self.total, 90)),
            **m,
        )


def evaluate(process: Process, policies: list[Policy] | Policy, *, reps: int = 200, years: float = 1.0,
             seed: int = 0) -> list[Evaluation]:
    """Simulate each policy and return its cost evaluation (same order as input)."""
    process.validate()
    if isinstance(policies, Policy):
        policies = [policies]
    if process.kind == "pass_fail" and any(p.check == "adjust" for p in policies):
        raise ValueError("'adjust' (re-aiming) only applies to measurement processes")
    # one simulation per distinct monitoring setup; finals are pure accounting
    keys: dict[tuple, int] = {}
    mon: list[Policy] = []
    for p in policies:
        k = p.monitoring_key()
        if k not in keys:
            keys[k] = len(mon)
            mon.append(p)
    groups: dict[float, list[int]] = {}
    for i, p in enumerate(mon):
        groups.setdefault(p.every_hours if p.check != "none" else 1.0, []).append(i)
    sims: dict[int, tuple[dict, int]] = {}
    for every, idx in groups.items():
        sim = _simulate_group(process, [mon[i] for i in idx], reps=reps, years=years,
                              seed=seed + int(every * 1000))
        for row, i in enumerate(idx):
            sims[i] = (sim, row)
    out = []
    for p in policies:
        sim, row = sims[keys[p.monitoring_key()]]
        a = _account(process, p, sim, row)
        metrics = {k: v for k, v in a.items() if k not in ("total", "parts")}
        out.append(Evaluation(p, a["total"], a["parts"], metrics))
    return out


def trace(process: Process, policy: Policy, *, hours: float = 80.0, seed: int = 3, resolution: float = 0.25) -> dict:
    """One simulated stretch of operation, for plotting ("a week in the life")."""
    process.validate()
    every = policy.every_hours if policy.check != "none" else 1.0
    substeps = max(1, int(round(every / resolution)))
    sim = _simulate_group(process, [policy], reps=1, years=hours / process.hours_per_year, seed=seed,
                          substeps=substeps, record=True)
    r = sim["record"]
    return {
        "t": r["t"],
        "level": r["level"][:, 0, 0],
        "active": r["active"][:, 0, 0],
        "check": r["check"],
        "signal": r["signal"][:, 0, 0],
        "false": r["false"][:, 0, 0],
        "ext": r["ext"][:, 0, 0],
    }
