"""Charts for the Learning Lab missions (same visual style as the rest of QualityLab)."""
from __future__ import annotations

import numpy as np

from ..plotting import CRITICAL, GRID, INK, INK_2, INK_3, SERIES, SERIES_2, ZONE, _style

GOOD = "#0ca30c"


def _fig(w=10, h=3.6):
    import matplotlib.pyplot as plt

    return plt.subplots(figsize=(w, h))


def bead_table_chart(days, limits: dict | None = None, ax=None, *, title="Red beads per worker per day",
                     split_at: int | None = None):
    """np chart of every lot, in production order (day by day, worker by worker)."""
    if ax is None:
        _, ax = _fig()
    _style(ax)
    labels, vals = [], []
    for d in days:
        for w, c in d.counts.items():
            labels.append(f"D{d.day}·{w[:3]}")
            vals.append(c)
    x = np.arange(1, len(vals) + 1)
    ax.plot(x, vals, color=SERIES, lw=1.8, marker="o", ms=5, zorder=3)
    if limits:
        for k, ls, col in (("ucl", (0, (5, 3)), INK), ("center", "-", INK_2), ("lcl", (0, (5, 3)), INK)):
            ax.axhline(limits[k], color=col, lw=1.2, ls=ls)
            ax.text(x[-1] + 0.6, limits[k], f" {k.upper() if k != 'center' else 'CL'} {limits[k]:.1f}",
                    va="center", fontsize=8, color=INK_2, clip_on=False)
        out = [(xi, v) for xi, v in zip(x, vals) if v > limits["ucl"] or v < limits["lcl"]]
        if out:
            ax.scatter(*zip(*out), s=110, facecolor="none", edgecolor=CRITICAL, lw=2, zorder=5)
    per_day = len(days[0].counts)
    for i in range(1, len(days)):
        ax.axvline(i * per_day + 0.5, color=GRID, lw=1)
    if split_at:
        ax.axvline(split_at + 0.5, color=INK_3, lw=1.2, ls=":")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_xlim(0.3, x[-1] + 0.7)
    ax.set_ylabel("red beads in a lot of 50", color=INK_2)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    return ax


def signal_chart(rnd, *, zones: bool, ax=None, reveal: bool = False):
    if ax is None:
        _, ax = _fig(10, 3.4)
    _style(ax)
    c = rnd.context
    mu, s = c["mu"], c["sigma"]
    v = np.asarray(rnd.values)
    x = np.arange(1, len(v) + 1)
    if zones:
        for k, a in ((1, 0.12), (2, 0.07)):
            ax.axhspan(mu - k * s, mu + k * s, color=ZONE, alpha=a, lw=0)
        for k in (1, 2):
            for sg in (-1, 1):
                ax.text(x[-1] + 0.6, mu + sg * k * s, f" {'+' if sg > 0 else '−'}{k}σ", va="center", fontsize=7,
                        color=INK_3, clip_on=False)
    ax.axhline(mu, color=INK_2, lw=1.2)
    for lim, nm in ((mu + 3 * s, "UCL"), (mu - 3 * s, "LCL")):
        ax.axhline(lim, color=INK, lw=1.2, ls=(0, (5, 3)))
        ax.text(x[-1] + 0.6, lim, f" {nm}", va="center", fontsize=8, color=INK_2, clip_on=False)
    ax.text(x[-1] + 0.6, mu, " CL", va="center", fontsize=8, color=INK_2, clip_on=False)
    ax.plot(x, v, color=SERIES, lw=1.8, marker="o", ms=4.5, zorder=3)
    if reveal and rnd.is_signal:
        ax.axvspan(rnd.start + 0.5, x[-1] + 0.5, color=SERIES_2, alpha=0.12, lw=0)
        first = min(min(i) for i in rnd.rules_fired.values())
        ax.scatter([x[first]], [v[first]], s=120, facecolor="none", edgecolor=CRITICAL, lw=2, zorder=5)
        ax.annotate("first signal", (x[first], v[first]), xytext=(0, 12), textcoords="offset points",
                    ha="center", fontsize=8, color=CRITICAL, fontweight="bold")
    pad = 4.2 * s
    lo = min(mu - pad, v.min() - 0.5 * s)
    hi = max(mu + pad, v.max() + 0.5 * s)
    ax.set_ylim(lo, hi)
    ax.set_xlim(0.3, x[-1] + 0.7)
    ax.set_xticks(x[::2])
    ax.set_xlabel(c.get("period", "day"), color=INK_2)
    ax.set_ylabel(c["unit"], color=INK_2)
    ax.set_title(c["name"], loc="left", fontsize=11, fontweight="bold", color=INK)
    return ax


def funnel_chart(fills, aims=None, target=12.0, ax=None, *, title="Bottle fills", lim=None, color=SERIES):
    if ax is None:
        _, ax = _fig(10, 3.2)
    _style(ax)
    x = np.arange(1, len(fills) + 1)
    ax.axhline(target, color=INK_2, lw=1.2)
    ax.plot(x, fills, color=color, lw=1.6, marker="o", ms=4, label="fill weight", zorder=3)
    if aims is not None:
        ax.step(x, aims, where="mid", color=INK_3, lw=1.2, ls=(0, (4, 2)), label="machine aim")
        ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK_2)
    if lim:
        ax.set_ylim(target - lim, target + lim)
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("bottle", color=INK_2)
    ax.set_ylabel("oz", color=INK_2)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    return ax


def capability_chart(mean, sigma, lsl, usl, target, ax=None, *, title=None, compare=None):
    from scipy import stats

    if ax is None:
        _, ax = _fig(10, 3.4)
    _style(ax)
    lo, hi = lsl - 0.035, usl + 0.035
    g = np.linspace(lo, hi, 600)
    y = stats.norm.pdf(g, mean, sigma)
    ax.fill_between(g, y, where=(g < lsl) | (g > usl), color=CRITICAL, alpha=0.35, lw=0)
    ax.plot(g, y, color=SERIES, lw=2, label="process")
    if compare is not None:
        m0, s0 = compare
        ax.plot(g, stats.norm.pdf(g, m0, s0), color=INK_3, lw=1.5, ls=(0, (4, 2)), label="before")
        ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK_2)
    for v, nm, col in ((lsl, "LSL", CRITICAL), (usl, "USL", CRITICAL), (target, "Target", INK_2)):
        ax.axvline(v, color=col, lw=1.4, ls="-" if nm != "Target" else ":")
        ax.text(v, ax.get_ylim()[1] * 0.97, f" {nm}", va="top", fontsize=8, color=col)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("shaft diameter (mm)", color=INK_2)
    if title:
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=INK)
    return ax


def quadrant_chart(x, ax, label):
    _style(ax)
    n = len(x)
    base = x[:12]
    m, s = base.mean(), base.std(ddof=1)
    ax.axhspan(-3, 3, color=GOOD, alpha=0.06, lw=0)
    ax.axhline(3, color=CRITICAL, lw=1.2)
    ax.axhline(-3, color=CRITICAL, lw=1.2)
    ax.axhline(m + 3 * s, color=INK, lw=1, ls=(0, (5, 3)))
    ax.axhline(m - 3 * s, color=INK, lw=1, ls=(0, (5, 3)))
    ax.plot(np.arange(1, n + 1), x, color=SERIES, lw=1.4, marker="o", ms=3)
    ax.set_ylim(-6.5, 6.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"Process {label}", loc="left", fontsize=10, fontweight="bold", color=INK)
    return ax


def pareto_pair(table, ax_count, ax_cost):
    for ax, col, ttl, fmt in ((ax_count, "complaints_per_year", "Ranked by number of complaints", "{:,.0f}"),
                              (ax_cost, "annual_cost", "Ranked by annual cost", "${:,.0f}")):
        _style(ax)
        t = table.sort_values(col, ascending=False)
        y = np.arange(len(t))[::-1]
        ax.barh(y, t[col], color=SERIES, height=0.6)
        for yi, v in zip(y, t[col]):
            ax.text(v, yi, " " + fmt.format(v), va="center", fontsize=8, color=INK_2)
        ax.set_yticks(y)
        ax.set_yticklabels(t.index, fontsize=8, color=INK)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
        ax.grid(False)
        ax.set_xlim(0, t[col].max() * 1.35)
        ax.set_title(ttl, loc="left", fontsize=10, fontweight="bold", color=INK)


def dprime_chart(phases: dict, ax=None):
    if ax is None:
        _, ax = _fig(6, 3)
    _style(ax)
    names = list(phases)
    vals = [phases[k] for k in names]
    ax.bar(names, vals, color=[INK_3, SERIES][: len(vals)], width=0.5)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9, color=INK)
    ax.axhline(0, color=INK_3, lw=1)
    ax.set_ylabel("d′ (sensitivity)", color=INK_2)
    ax.set_title("Telling signal from noise", loc="left", fontsize=11, fontweight="bold", color=INK)
    return ax





# ---------------------------------------------------------------------------
# Process Lab
# ---------------------------------------------------------------------------

CHANGE_COLORS = {"shift": "#eb6834", "drift": "#8a5cd6", "spread": "#0f9e8e", "outlier": "#b5832a"}


def process_lab_figure(exp, r):
    """Top: what really happened (every unit, the true average, spec limits).
    Middle: what the chart saw (limits, baseline, signals, fixes). Bottom: the spread chart, if any."""
    import matplotlib.pyplot as plt

    P = exp.process
    main, disp = r["main"], r["disp"]
    m = P.samples
    x = np.arange(1, m + 1)
    rows = 3 if disp is not None and exp.monitor.chart == "shewhart" else 2
    fig, axs = plt.subplots(rows, 1, figsize=(11, 2.9 * rows + 0.4), sharex=True,
                            gridspec_kw=dict(height_ratios=[1.15] + [1] * (rows - 1)))
    for ax in axs:
        _style(ax)
        ax.axvspan(0.5, P.baseline + 0.5, color=GRID, alpha=0.55, lw=0, zorder=0)
        for c in exp.changes:
            ax.axvline(c.at - 0.5, color=CHANGE_COLORS.get(c.kind, INK_3), lw=1.4, ls=(0, (4, 2)), zorder=1)

    # 1 · reality
    ax = axs[0]
    X = r["X"]
    xs = np.repeat(x, X.shape[1])
    ax.scatter(xs, X.ravel(), s=6, color=INK_3, alpha=0.45, lw=0, zorder=2, label="each unit measured")
    ax.fill_between(x, r["mu"] - 3 * r["sd"], r["mu"] + 3 * r["sd"], step="mid", color=SERIES_2, alpha=0.12, lw=0,
                    zorder=1, label="true range of 99.7 % of units")
    ax.plot(x, r["mu"], color=SERIES_2, lw=2.2, zorder=4, drawstyle="steps-mid", label="true process average")
    for lim, nm in ((P.lsl, "LSL"), (P.usl, "USL")):
        if lim is not None:
            ax.axhline(lim, color=CRITICAL, lw=1.3, ls=(0, (6, 3)))
            ax.text(m + 0.8, lim, f" {nm}", va="center", fontsize=8, color=CRITICAL, clip_on=False)
    ax.axhline(P.target, color=INK_3, lw=0.8)
    ax.set_ylabel(P.unit, color=INK_2)
    ax.set_title("What really happened", loc="left", fontsize=11, fontweight="bold", color=INK)
    from matplotlib.patches import Patch

    baseline_patch = Patch(facecolor=GRID, alpha=0.9, label="baseline (setting up the chart)")
    for c in exp.changes:
        ax.text(c.at - 0.3, 1.0, c.kind, transform=ax.get_xaxis_transform(), ha="left", va="bottom", fontsize=8,
                color=CHANGE_COLORS.get(c.kind, INK_3), fontweight="bold")
    handles, _ = ax.get_legend_handles_labels()
    ax.legend(handles=handles + [baseline_patch], loc="upper left", bbox_to_anchor=(0, -0.02), fontsize=8,
              frameon=False, ncol=4)

    # 2 · the chart
    ax = axs[1]
    stat = main.statistic
    if main.kind == "cusum":
        ax.plot(x, stat, color=SERIES, lw=1.6, marker="o", ms=3, label="C⁺ (upward)")
        ax.plot(x, main.extra["C_minus"], color=SERIES_2, lw=1.6, marker="o", ms=3, label="−C⁻ (downward)")
        H = main.params["H"]
        for v in (H, -H):
            ax.axhline(v, color=INK, lw=1.2, ls=(0, (5, 3)))
        ax.axhline(0, color=INK_2, lw=1)
        ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
        pts = np.where(np.abs(stat) >= np.abs(main.extra["C_minus"]), stat, main.extra["C_minus"])
    else:
        ax.plot(x, stat, color=SERIES, lw=1.6, marker="o", ms=3.5, zorder=3)
        ax.plot(x, main.center, color=INK_2, lw=1.1)
        ax.plot(x, main.ucl, color=INK, lw=1.2, ls=(0, (5, 3)))
        ax.plot(x, main.lcl, color=INK, lw=1.2, ls=(0, (5, 3)))
        for v, nm in ((main.ucl[-1], "UCL"), (main.center[-1], "CL"), (main.lcl[-1], "LCL")):
            ax.text(m + 0.8, v, f" {nm}", va="center", fontsize=8, color=INK_2, clip_on=False)
        pts = stat
    sig = np.array(r["signals"], int) - 1
    own = np.intersect1d(sig, main.out_of_control)
    if own.size:
        ax.scatter(x[own], pts[own], s=95, facecolor="none", edgecolor=CRITICAL, lw=2, zorder=5)
    for s in r["fixed"].values():
        ax.annotate("fixed", (s, 1.0), xycoords=("data", "axes fraction"), ha="center", va="bottom", fontsize=8,
                    color=GOOD, fontweight="bold")
        ax.axvline(s + 0.5, color=GOOD, lw=1.2)
    name = {"Xbar": "X̄ chart (sample averages)", "I": "Individuals chart", "EWMA": "EWMA chart of sample averages",
            "CUSUM": "CUSUM chart of sample averages"}.get(main.name, main.name)
    if exp.process.n == 1 and main.name in ("EWMA", "CUSUM"):
        name = name.replace(" of sample averages", "")
    ax.set_title(f"What your chart saw: {name}", loc="left", fontsize=11, fontweight="bold", color=INK)

    # 3 · spread
    if rows == 3:
        ax = axs[2]
        ax.plot(x, disp.statistic, color=SERIES, lw=1.4, marker="o", ms=3)
        ax.plot(x, disp.center, color=INK_2, lw=1.1)
        ax.plot(x, disp.ucl, color=INK, lw=1.2, ls=(0, (5, 3)))
        if np.any(disp.lcl > 0):
            ax.plot(x, disp.lcl, color=INK, lw=1.2, ls=(0, (5, 3)))
        o = disp.out_of_control
        if o.size:
            ax.scatter(x[o], disp.statistic[o], s=95, facecolor="none", edgecolor=CRITICAL, lw=2, zorder=5)
        ax.set_title(f"Spread within each sample ({disp.name} chart)", loc="left", fontsize=11, fontweight="bold",
                     color=INK)
    axs[-1].set_xlabel("sample number", color=INK_2)
    axs[-1].set_xlim(0.3, m + 0.7)
    fig.tight_layout()
    return fig


def replication_figure(rep, exp):
    """Histogram of detection delays for each change across many runs."""
    import matplotlib.pyplot as plt

    k = len(rep["changes"])
    fig, axs = plt.subplots(1, max(1, k), figsize=(5.2 * max(1, k), 2.9), squeeze=False)
    for j, ax in enumerate(axs[0]):
        _style(ax)
        if k == 0:
            ax.text(0.5, 0.5, "No changes in this experiment", ha="center", va="center", transform=ax.transAxes,
                    color=INK_2)
            ax.set_xticks([])
            ax.set_yticks([])
            continue
        d = np.array(rep["changes"][j]["delays"])
        c = exp.changes[j]
        if d.size:
            bins = np.arange(0.5, d.max() + 1.5, max(1, int(np.ceil(d.max() / 30))))
            ax.hist(d, bins=bins, color=CHANGE_COLORS.get(c.kind, SERIES), alpha=0.85)
            ax.axvline(np.median(d), color=INK, lw=1.4, ls=(0, (4, 2)))
        ax.set_title(f"{c.kind} at sample {c.at}: caught in {rep['changes'][j]['detected']:.0%} of {rep['reps']} runs",
                     loc="left", fontsize=10, fontweight="bold", color=INK)
        ax.set_xlabel("samples until the chart signaled", color=INK_2)
        ax.set_ylabel("runs", color=INK_2)
    fig.tight_layout()
    return fig
