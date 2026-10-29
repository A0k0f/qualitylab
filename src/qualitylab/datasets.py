"""Simulated teaching datasets with business settings.

Every dataset is generated from a seed, so an instructor can hand each
student (or each semester) a different version of the same scenario: the
special causes land at different points, with different sizes. With the
default ``seed=None`` you get the canonical version used in the README and
labs (seed 445).

``answer_key(name, seed)`` returns what was planted, for grading.

All data here are SIMULATED. They are realistic in structure, not real
company records.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_SEED = 445


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    story: str
    chart: str
    columns: str
    make: Callable[[np.random.Generator], tuple[pd.DataFrame, dict]]
    specs: dict | None = None
    default_seed: int = DEFAULT_SEED
    check: Callable[[pd.DataFrame, dict], bool] | None = None


def _coffee_fill(rng):
    m, n, mu, sd = 30, 5, 12.00, 0.04
    shift_at = int(rng.integers(17, 23))
    shift = float(rng.choice([1.0, 1.25, 1.5])) * sd
    spike_at = int(rng.integers(4, 12))
    X = rng.normal(mu, sd, (m, n))
    X[shift_at:] += shift
    # loose nozzle: one subgroup with a much larger spread
    X[spike_at] = mu + rng.normal(0, sd, n)
    hi, lo = rng.choice(n, 2, replace=False)
    X[spike_at, hi] = mu + 4.2 * sd
    X[spike_at, lo] = mu - 3.8 * sd
    X = X.round(3)
    start = pd.Timestamp("2026-09-01 07:00")
    df = pd.DataFrame(X, columns=[f"bottle_{j + 1}" for j in range(n)])
    df.insert(0, "sample_time", [start + pd.Timedelta(hours=2 * i) for i in range(m)])
    df.index = pd.RangeIndex(1, m + 1, name="sample")
    key = dict(mean_shift_starts_at_sample=shift_at + 1, shift_oz=round(shift, 3),
               high_spread_sample=spike_at + 1, true_mean=mu, true_sigma=sd)
    return df, key


def _call_wait(rng):
    m, mu, sd = 60, 4.0, 0.5
    drift_from = int(rng.integers(32, 41))
    slope = float(rng.choice([0.04, 0.05, 0.06]))
    z = rng.standard_normal(m)
    x = mu + sd * (z - z.mean()) / z.std(ddof=1)  # noise standardized so short series behave "typically"
    t = np.arange(m)
    x += np.where(t >= drift_from, slope * (t - drift_from + 1), 0) * sd / 0.5
    df = pd.DataFrame({"date": pd.bdate_range("2026-06-01", periods=m),
                       "avg_wait_minutes": x.round(2)})
    df.index = pd.RangeIndex(1, m + 1, name="day")
    key = dict(drift_starts_on_day=drift_from + 1, drift_minutes_per_day=round(slope, 3),
               true_mean=mu, true_sigma=sd)
    return df, key


def _invoice_errors(rng):
    m, p = 26, 0.04
    n = rng.integers(180, 321, m)
    bad = int(rng.integers(8, 22))
    pp = np.full(m, p)
    pp[bad] = float(rng.choice([0.10, 0.12, 0.14]))
    d = rng.binomial(n, pp)
    df = pd.DataFrame({"week_starting": pd.date_range("2026-03-02", periods=m, freq="W-MON"),
                       "invoices_audited": n, "invoices_with_errors": d})
    df.index = pd.RangeIndex(1, m + 1, name="week")
    key = dict(problem_week=bad + 1, problem_rate=pp[bad], baseline_rate=p)
    return df, key


def _online_orders(rng):
    """Huge samples with week-to-week variation in the true rate (overdispersion)."""
    m = 30
    n = rng.integers(18000, 42000, m)
    p_true = rng.beta(400, 9600, m)  # mean 0.04, small real week-to-week wobble
    bad = int(rng.integers(12, 26))
    p_true[bad] *= 1.5
    d = rng.binomial(n, p_true)
    df = pd.DataFrame({"week_starting": pd.date_range("2026-01-05", periods=m, freq="W-MON"),
                       "orders_shipped": n, "orders_returned": d})
    df.index = pd.RangeIndex(1, m + 1, name="week")
    key = dict(real_problem_week=bad + 1, note="standard p chart flags many weeks; Laney p' should flag ~1")
    return df, key


def _pcb_defects(rng):
    m, c = 26, 6.0
    x = rng.poisson(c, m)
    bad = int(rng.integers(5, 20))
    x[bad] = int(rng.integers(16, 21))
    df = pd.DataFrame({"board_id": [f"PCB-{1040 + i}" for i in range(m)], "defects": x})
    df.index = pd.RangeIndex(1, m + 1, name="board")
    key = dict(bad_board=bad + 1, bad_board_id=f"PCB-{1040 + bad}", baseline_defects_per_board=c)
    return df, key


def _hotel_complaints(rng):
    m = 30
    nights = rng.integers(2400, 6200, m)
    u0 = 4.0 / 1000
    change = int(rng.integers(12, 17))
    u = np.where(np.arange(m) >= change, u0 * float(rng.choice([0.5, 0.55, 0.6])), u0)
    x = rng.poisson(u * nights)
    df = pd.DataFrame({"month": pd.period_range("2024-01", periods=m, freq="M").astype(str),
                       "guest_nights_thousands": (nights / 1000).round(3), "complaints": x})
    df.index = pd.RangeIndex(1, m + 1, name="period")
    key = dict(training_program_month=change + 1, rate_before_per_1000=4.0,
               rate_after_per_1000=round(u[-1] * 1000, 2))
    return df, key


def _complaint_reasons(rng):
    cats = {
        "Late delivery": 0.36, "Wrong item shipped": 0.21, "Damaged packaging": 0.16,
        "Billing error": 0.12, "Rude support agent": 0.04, "Website checkout bug": 0.04,
        "Missing parts": 0.03, "Hard-to-read instructions": 0.02, "Other": 0.02,
    }
    p = np.array(list(cats.values()))
    p = rng.dirichlet(p * 3000)  # mild variation between versions; the ranking of the top four is stable
    n = int(rng.integers(900, 1201))
    reason = rng.choice(list(cats), size=n, p=p)
    dates = pd.Timestamp("2026-07-01") + pd.to_timedelta(rng.integers(0, 92, n), unit="D")
    df = pd.DataFrame({"date": dates, "complaint_reason": reason}).sort_values("date").reset_index(drop=True)
    df.index = pd.RangeIndex(1, n + 1, name="complaint")
    return df, dict(category_shares=dict(zip(cats, p.round(3))))


def _shaft_diameter(rng):
    m, n = 25, 4
    mu = 25.000 + float(rng.choice([0.010, 0.012, 0.015]))
    sd = float(rng.choice([0.011, 0.012, 0.013]))
    X = rng.normal(mu, sd, (m, n)).round(4)
    df = pd.DataFrame(X, columns=[f"part_{j + 1}" for j in range(n)])
    df.index = pd.RangeIndex(1, m + 1, name="subgroup")
    cp = 0.10 / (6 * sd)
    cpk = min(25.05 - mu, mu - 24.95) / (3 * sd)
    return df, dict(true_mean=mu, true_sigma=sd, true_Cp=round(cp, 3), true_Cpk=round(cpk, 3))


def _bottling_line(rng):
    """Three correlated quality characteristics; one point breaks the correlation."""
    m = 40
    mean = np.array([500.0, 2.10, 85.0])  # fill (ml), cap torque (N·m), seal temp (°C)
    sd = np.array([1.5, 0.08, 1.2])
    R = np.array([[1, 0.8, 0.6], [0.8, 1, 0.7], [0.6, 0.7, 1]])
    S = R * np.outer(sd, sd)
    X = rng.multivariate_normal(mean, S, m)
    odd = int(rng.integers(20, 36))
    # each variable within ±2σ of its mean, but in a combination the correlation makes very unlikely
    X[odd] = mean + np.array([1.9, -1.9, 1.6]) * sd
    df = pd.DataFrame(X.round(3), columns=["fill_ml", "cap_torque_Nm", "seal_temp_C"])
    df.index = pd.RangeIndex(1, m + 1, name="bottle")
    return df, dict(unusual_bottle=odd + 1, note="each variable is inside its own 3-sigma limits")


# ---------------------------------------------------------------------------
# Each generated dataset is checked so that, with the settings the labs use,
# the planted story is visible and there are no false alarms in the reference
# period. Draws that fail are regenerated (deterministically for a given seed).
# Real data are messier; these are teaching datasets.
# ---------------------------------------------------------------------------

def _first(res, phase2_only=False):
    f = res.first_signal(phase2_only=phase2_only)
    return np.inf if f is None else f


def _check_coffee(df, key):
    from .charts import xbar_r

    spike, shift = key["high_spread_sample"] - 1, key["mean_shift_starts_at_sample"] - 1
    X = df.filter(like="bottle")
    xr, rr = xbar_r(X, phase1=15, exclude=[spike])
    xr2, rr2 = xbar_r(X, phase1=15, revise=True)
    return (spike in rr.violations[1] and bool(rr2.excluded[spike]) and rr2.excluded.sum() == 1
            and shift <= _first(xr) < shift + 6 and rr.out_of_control.tolist() == [spike])


def _check_call_wait(df, key):
    from .charts import cusum, ewma, imr

    x, d = df["avg_wait_minutes"], key["drift_starts_on_day"] - 1
    fe, fc = _first(ewma(x, phase1=30)), _first(cusum(x, phase1=30))
    fi = _first(imr(x, phase1=30, rules="limits")[0])
    return d <= fe < 58 and d <= fc < 58 and fi >= d and min(fe, fc) + 3 <= fi


def _check_invoice(df, key):
    from .charts import p_chart

    p = p_chart(df["invoices_with_errors"], df["invoices_audited"])
    return p.out_of_control.tolist() == [key["problem_week"] - 1]


def _check_online(df, key):
    from .charts import p_chart

    std = p_chart(df["orders_returned"], df["orders_shipped"])
    lan = p_chart(df["orders_returned"], df["orders_shipped"], laney=True)
    return len(std.violations[1]) >= 4 and lan.violations[1].tolist() == [key["real_problem_week"] - 1]


def _check_pcb(df, key):
    from .charts import c_chart

    return c_chart(df["defects"]).out_of_control.tolist() == [key["bad_board"] - 1]


def _check_hotel(df, key):
    from .charts import u_chart

    u = u_chart(df["complaints"], df["guest_nights_thousands"], phase1=12)
    t = key["training_program_month"] - 1
    return (not u.phase1[u.out_of_control].any() and t <= _first(u) <= t + 10
            and len(u.violations.get(2, [])) > 0)


def _check_shaft(df, key):
    from .charts import xbar_r

    return all(r.in_control for r in xbar_r(df))


def _check_bottling(df, key):
    from .charts import imr
    from .multivariate import hotelling_t2

    odd = key["unusual_bottle"] - 1
    if hotelling_t2(df).out_of_control.tolist() != [odd]:
        return False
    return all(imr(df[c], rules="limits")[0].in_control for c in df.columns)


SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in [
        Scenario("coffee_fill", "Cold-brew bottle fill volume",
                 "A beverage plant fills 12-oz bottles of cold brew. Every two hours, a technician "
                 "pulls 5 consecutive bottles and weighs the fill (oz). Spec: 11.88–12.12 oz.",
                 "Xbar-R", "bottle_1..bottle_5 = fill volume (oz) of 5 bottles per sample",
                 _coffee_fill, dict(lsl=11.88, usl=12.12, target=12.0), check=_check_coffee),
        Scenario("call_wait", "Call-center average wait",
                 "A bank's customer-service center records the average time callers wait before "
                 "reaching an agent, once per business day (minutes).",
                 "I-MR (try EWMA/CUSUM too)", "avg_wait_minutes = one value per day", _call_wait,
                 dict(usl=6.0), check=_check_call_wait),
        Scenario("invoice_errors", "Accounts-payable invoice errors",
                 "An accounts-payable team audits a sample of invoices each week and counts those with "
                 "any error (wrong amount, vendor, PO, or tax code). The sample size varies.",
                 "p chart", "invoices_with_errors out of invoices_audited", _invoice_errors,
                 check=_check_invoice),
        Scenario("online_orders", "E-commerce returns (very large samples)",
                 "An online retailer tracks the share of shipped orders that are returned, every week. "
                 "Tens of thousands of orders ship weekly.",
                 "Laney p' chart (compare with a standard p chart)", "orders_returned out of orders_shipped",
                 _online_orders, check=_check_online),
        Scenario("pcb_defects", "Circuit-board defects",
                 "An electronics assembler inspects each finished printed circuit board and counts "
                 "solder and placement defects. All boards are the same model.",
                 "c chart", "defects = count on each board", _pcb_defects, check=_check_pcb),
        Scenario("hotel_complaints", "Hotel guest complaints",
                 "A hotel group logs guest complaints each month. Occupancy varies, so complaints are "
                 "compared per 1,000 guest-nights. A front-desk training program ran at some point.",
                 "u chart", "complaints over guest_nights_thousands", _hotel_complaints,
                 check=_check_hotel),
        Scenario("complaint_reasons", "Customer complaint reasons",
                 "Every complaint received by an online furniture store last quarter, with its "
                 "primary reason.", "Pareto chart", "complaint_reason = category of each complaint",
                 _complaint_reasons),
        Scenario("shaft_diameter", "Machined shaft diameter",
                 "A machine shop turns steel shafts. Four consecutive parts are measured each hour (mm). "
                 "Spec: 25.00 ± 0.05 mm.", "Capability (after X̄-R shows stability)",
                 "part_1..part_4 = diameters (mm)", _shaft_diameter,
                 dict(lsl=24.95, usl=25.05, target=25.0), check=_check_shaft),
        Scenario("bottling_line", "Bottling line: three related measurements",
                 "Fill volume, cap torque and seal temperature on a bottling line tend to move together. "
                 "One value per bottle sampled.", "Hotelling T² (compare with three I charts)",
                 "fill_ml, cap_torque_Nm, seal_temp_C", _bottling_line, check=_check_bottling),
    ]
}


def _get(name: str) -> Scenario:
    try:
        return SCENARIOS[name]
    except KeyError:
        raise KeyError(f"unknown dataset {name!r}; available: {list(SCENARIOS)}") from None


def _seed(name: str, seed) -> int:
    if seed is None:
        return _get(name).default_seed
    if isinstance(seed, str):
        # hash the whole code (case/space-insensitive) so similar codes give unrelated data
        digest = hashlib.sha256(seed.strip().lower().encode()).digest()
        return int.from_bytes(digest[:8], "big")
    return int(seed)


def _generate(name: str, seed) -> tuple[pd.DataFrame, dict]:
    sc = _get(name)
    rng = np.random.default_rng(_seed(name, seed))
    for _ in range(500):
        df, key = sc.make(rng)
        if sc.check is None or sc.check(df, key):
            return df, key
    raise RuntimeError(f"could not generate a valid {name!r} dataset")  # pragma: no cover


def load(name: str, seed: int | str | None = None) -> pd.DataFrame:
    """Load a simulated dataset. ``seed`` may be an int or any string (e.g. a student ID)."""
    df, _ = _generate(name, seed)
    df.attrs["scenario"] = name
    return df


def answer_key(name: str, seed: int | str | None = None) -> dict:
    """What was planted in the dataset (for instructors)."""
    _, key = _generate(name, seed)
    return key


def info(name: str | None = None) -> pd.DataFrame | Scenario:
    if name is not None:
        return _get(name)
    return pd.DataFrame(
        [dict(name=s.name, title=s.title, chart=s.chart, columns=s.columns) for s in SCENARIOS.values()]
    ).set_index("name")


def available() -> list[str]:
    return list(SCENARIOS)
