"""Charts for the what-if simulator (matplotlib, same style as qualitylab.plotting)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .plotting import CRITICAL, GRID, INK, INK_2, INK_3, SERIES, SERIES_2, SURFACE, _style

# categorical slots in fixed order (validated: adjacent CVD ΔE ≥ 9.1)
PART_COLORS = {
    "Routine checks": "#2a78d6",
    "False alarms": "#eb6834",
    "Fixing real problems": "#1baf7a",
    "100% inspection": "#eda100",
    "Scrap / rework": "#e87ba4",
    "Defects reaching customers": "#008300",
    "Giveaway (overfill)": "#6250d6",
}
GOOD = "#0ca30c"
WARN = "#c98500"


def _money_fmt(x, _pos=None):
    sign = "-" if x < 0 else ""
    a = abs(x)
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.0f}k"
    return f"{sign}${a:.0f}"


def plot_cost_breakdown(breakdown: pd.DataFrame, ax=None, *, title="Where the money goes (expected per year)"):
    """Stacked horizontal bars: one bar per plan, one segment per cost type."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    cols = [c for c in PART_COLORS if c in breakdown.columns and breakdown[c].abs().sum() > 0]
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 0.75 * len(breakdown) + 1.6))
    _style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    y = np.arange(len(breakdown))[::-1]
    left = np.zeros(len(breakdown))
    for c in cols:
        v = breakdown[c].to_numpy()
        ax.barh(y, v, left=left, color=PART_COLORS[c], height=0.6, edgecolor=SURFACE, linewidth=1.5, label=c)
        left += v
    for yi, tot in zip(y, left):
        ax.text(tot, yi, "  " + _money_fmt(tot), va="center", fontsize=9, color=INK, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(breakdown.index, fontsize=9, color=INK)
    ax.xaxis.set_major_formatter(FuncFormatter(_money_fmt))
    ax.set_xlim(0, left.max() * 1.18)
    ax.legend(frameon=False, fontsize=8, ncol=min(4, len(cols)), loc="upper left", bbox_to_anchor=(0, -0.12),
              labelcolor=INK_2)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    return ax


def plot_trace(tr: dict, process, ax=None, *, title="A simulated stretch of operation"):
    """Process level over time, problem periods, checks, catches and false alarms."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 3.4))
    _style(ax)
    t, lvl, act = tr["t"], tr["level"], tr["active"]
    meas = process.kind == "measurement"
    y = lvl if meas else lvl * 100
    # shade problem periods
    dt = t[1] - t[0] if len(t) > 1 else 1
    starts = np.flatnonzero(act & ~np.concatenate([[False], act[:-1]]))
    ends = np.flatnonzero(act & ~np.concatenate([act[1:], [False]]))
    for s, e in zip(starts, ends):
        ax.axvspan(t[s] - dt, t[e], color=SERIES_2, alpha=0.13, lw=0,
                   label="problem present" if s == starts[0] else None)
    ax.plot(t, y, color=SERIES, lw=1.8, label="process average" if meas else "error rate (%)")
    if meas:
        span = t[-1] - t[0] if len(t) > 1 else 1
        ax.set_xlim(0, t[-1] + 0.07 * span)
        for v, nm in ((process.lsl, "LSL"), (process.usl, "USL")):
            if v is not None:
                ax.axhline(v, color=CRITICAL, lw=1.2, ls=(0, (5, 3)), xmax=1 / 1.07)
                ax.text(t[-1] + 0.01 * span, v, nm, va="center", fontsize=8, color=CRITICAL)
        if process.target is not None:
            ax.axhline(process.target, color=INK_3, lw=1, ls=":")
    ymin, ymax = ax.get_ylim()
    base = ymin
    chk = tr["check"]
    ax.scatter(t[chk], np.full(chk.sum(), base), marker="|", s=40, color=INK_3, label="check", zorder=2)
    caught = tr["signal"] & ~tr["false"]
    ax.scatter(t[caught], y[caught], marker="^", s=70, color=GOOD, edgecolor=SURFACE, zorder=5,
               label="problem caught by a check")
    ax.scatter(t[tr["false"]], y[tr["false"]], marker="X", s=60, color=WARN, edgecolor=SURFACE, zorder=5,
               label="false alarm")
    ax.scatter(t[tr["ext"]], y[tr["ext"]], marker="D", s=50, color=CRITICAL, edgecolor=SURFACE, zorder=5,
               label="problem noticed late (customer, report)")
    ax.set_xlabel("operating hours", color=INK_2)
    ax.set_ylabel(process.unit_label or ("average" if meas else "error rate, %"), color=INK_2)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left", bbox_to_anchor=(0, -0.2), labelcolor=INK_2)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    return ax


def plot_frontier(table: pd.DataFrame, highlights: dict[str, str], ax=None):
    """Every plan: annual cost vs defects reaching customers; a few highlighted."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 4.2))
    _style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.scatter(table["escapes_ppm"], table["annual_cost"], s=14, color=INK_3, alpha=0.45, lw=0,
               label="other plans")
    colors = [SERIES, SERIES_2, "#1baf7a"]
    markers = ["o", "s", "D"]
    for (name, pol), c, m in zip(highlights.items(), colors, markers):
        r = table[table["policy"] == pol]
        if len(r):
            ax.scatter(r["escapes_ppm"], r["annual_cost"], s=110, color=c, marker=m, edgecolor=SURFACE, lw=1.5,
                       zorder=5, label=name)
            ax.annotate(name, (r["escapes_ppm"].iloc[0], r["annual_cost"].iloc[0]), xytext=(8, 6),
                        textcoords="offset points", fontsize=9, color=INK, fontweight="bold")
    ax.yaxis.set_major_formatter(FuncFormatter(_money_fmt))
    hi = table["annual_cost"].quantile(0.95)
    ax.set_ylim(table["annual_cost"].min() * 0.9, max(hi, *[table.loc[table["policy"] == p, "annual_cost"].max()
                                                             for p in highlights.values() if (table["policy"] == p).any()]) * 1.08)
    ax.set_xlabel("defects reaching customers (per million units)", color=INK_2)
    ax.set_ylabel("expected annual cost", color=INK_2)
    ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK_2)
    ax.set_title("Every plan tested: cost vs. customer impact (lower-left is better)", loc="left", fontsize=11,
                 fontweight="bold", color=INK)
    return ax


def plot_tornado(sens: pd.DataFrame, base_saving: float, ax=None, *, low=0.5, high=1.5):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 0.6 * len(sens) + 1.4))
    _style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    y = np.arange(len(sens))[::-1]
    for yi, (_, r) in zip(y, sens.iterrows()):
        lo, hi = r["savings_low"], r["savings_high"]
        ax.barh(yi, lo - base_saving, left=base_saving, color="#86b6ef", height=0.55, edgecolor=SURFACE)
        ax.barh(yi, hi - base_saving, left=base_saving, color="#1c5cab", height=0.55, edgecolor=SURFACE)
        if abs(hi - lo) < 0.03 * max(abs(base_saving), 1):
            ax.text(max(lo, hi), yi, "  barely matters", va="center", ha="left", fontsize=8, color=INK_2)
            continue
        for v, tag in ((lo, f"×{low:g}"), (hi, f"×{high:g}")):
            ax.text(v, yi, f" {tag}: {_money_fmt(v)} ", va="center", ha="left" if v >= base_saving else "right",
                    fontsize=8, color=INK_2)
    ax.axvline(base_saving, color=INK, lw=1.2)
    ax.axvline(0, color=CRITICAL, lw=1, ls=":")
    ax.set_yticks(y)
    ax.set_yticklabels(sens["input"], fontsize=9, color=INK)
    ax.xaxis.set_major_formatter(FuncFormatter(_money_fmt))
    span = max(abs(sens[["savings_low", "savings_high"]].to_numpy() - base_saving).max(), abs(base_saving) * 0.2)
    ax.set_xlim(min(0, base_saving - span * 1.6), base_saving + span * 1.6)
    ax.set_title("Annual saving if an input is half / 1.5× your estimate", loc="left", fontsize=11,
                 fontweight="bold", color=INK)
    return ax


def plot_aim(aim: dict, process, ax=None):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    tab = aim["table"]
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 3.6))
    _style(ax)
    lo = (process.lsl if process.lsl is not None else tab["aim"].min()) - process.sigma
    hi = (process.usl if process.usl is not None else tab["aim"].max()) + process.sigma
    m = (tab["aim"] >= lo) & (tab["aim"] <= hi)
    ax.plot(tab.loc[m, "aim"], tab.loc[m, "annual_cost"], color=SERIES, lw=2)
    ax.set_yscale("symlog", linthresh=max(1.0, aim["annual_cost_best"]))
    right = aim["current_aim"] >= aim["best_aim"]
    for v, nm, c, off in ((aim["current_aim"], "today", SERIES_2, (12, 18) if right else (-12, 18)),
                          (aim["best_aim"], "best", GOOD, (-12, -30) if right else (12, -30))):
        yv = np.interp(v, tab["aim"], tab["annual_cost"])
        ax.scatter([v], [yv], s=90, color=c, edgecolor=SURFACE, zorder=5)
        ax.annotate(f"{nm}: {v:.4g} → {_money_fmt(yv)}/yr", (v, yv), xytext=off, textcoords="offset points",
                    fontsize=9, color=INK, fontweight="bold", ha="left" if off[0] > 0 else "right")
    for v, nm in ((process.lsl, "LSL"), (process.usl, "USL")):
        if v is not None:
            ax.axvline(v, color=CRITICAL, lw=1.2, ls=(0, (5, 3)))
            ax.text(v, ax.get_ylim()[1], f" {nm}", va="top", fontsize=8, color=CRITICAL)
    ax.yaxis.set_major_formatter(FuncFormatter(_money_fmt))
    ax.set_xlabel(f"process setting (average){' in ' + process.unit_label if process.unit_label else ''}", color=INK_2)
    ax.set_ylabel("cost per year (log)", color=INK_2)
    ax.set_title("Where to aim the process: overfill vs. out-of-spec risk", loc="left", fontsize=11,
                 fontweight="bold", color=INK)
    return ax
