"""Matplotlib renderings with a consistent, accessible style.

Signals are shown with *shape and label* (a ring plus the rule number), not
color alone, so the charts survive grayscale printing and color-vision
differences.
"""
from __future__ import annotations

import numpy as np

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_3 = "#8a8983"
GRID = "#e8e7e3"
SERIES = "#2a78d6"
SERIES_2 = "#eb6834"
CRITICAL = "#d03b3b"
ZONE = "#2a78d6"


def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_3)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _xpos(res):
    return np.arange(1, len(res.statistic) + 1)


def _step(ax, x, y, **kw):
    if np.allclose(y, y[0], equal_nan=True):
        ax.axhline(y[0], **kw)
    else:
        ax.step(x, y, where="mid", **kw)


def plot_chart(res, ax=None, *, show_zones: bool = True, annotate: bool = True,
               title: str | None = None, ylabel: str | None = None, xtick_labels: bool = True):
    """Draw a :class:`~qualitylab.result.ChartResult`."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 3.6))
    _style(ax)
    x = _xpos(res)
    y = res.statistic

    if res.kind == "cusum":
        ax.plot(x, y, color=SERIES, lw=2, marker="o", ms=4.5, label="C⁺ (upward)")
        ax.plot(x, res.extra["C_minus"], color=SERIES_2, lw=2, marker="s", ms=4.5, label="−C⁻ (downward)")
        ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK_2)
    else:
        if show_zones and res.kind in ("shewhart", "attribute") and np.isfinite(res.sigma).all():
            for k, a in ((1, 0.10), (2, 0.06)):
                ax.fill_between(x, res.center - k * res.sigma, res.center + k * res.sigma,
                                step="mid", color=ZONE, alpha=a, lw=0)
        if res.kind == "ewma" and "x" in res.extra:
            ax.plot(x, res.extra["x"], color=INK_3, lw=0, marker=".", ms=4, label="observations")
        ax.plot(x, y, color=SERIES, lw=2, marker="o", ms=4.5, zorder=3,
                label="EWMA" if res.kind == "ewma" else None)
        if res.kind == "ewma":
            ax.legend(frameon=False, fontsize=9, loc="upper left", labelcolor=INK_2)

    _step(ax, x, res.center, color=INK_2, lw=1.2)
    _step(ax, x, res.ucl, color=INK, lw=1.2, ls=(0, (5, 3)))
    if res.kind != "t2":
        _step(ax, x, res.lcl, color=INK, lw=1.2, ls=(0, (5, 3)))

    # excluded Phase I points: hollow
    ex = np.flatnonzero(res.excluded)
    if ex.size:
        ax.scatter(x[ex], y[ex], s=60, facecolor=SURFACE, edgecolor=SERIES, lw=1.5, zorder=4)

    # signals: ring + rule number
    flagged: dict[int, list[int]] = {}
    for rule, pos in res.violations.items():
        for i in pos:
            flagged.setdefault(int(i), []).append(rule)
    if flagged:
        fi = np.array(sorted(flagged))
        yy = y[fi]
        if res.kind == "cusum":
            yy = np.where(res.statistic[fi] > res.ucl[fi], res.statistic[fi], res.extra["C_minus"][fi])
        ax.scatter(x[fi], yy, s=110, facecolor="none", edgecolor=CRITICAL, lw=2, zorder=5)
        ax.scatter(x[fi], yy, s=26, color=CRITICAL, zorder=6)
        if annotate and res.kind not in ("cusum", "t2", "ewma"):
            for i, yi in zip(fi, yy):
                ax.annotate(",".join(map(str, sorted(flagged[i]))), (x[i], yi), xytext=(0, 9),
                            textcoords="offset points", ha="center", fontsize=8, color=CRITICAL,
                            fontweight="bold")

    # phase divider
    if (~res.phase1).any() and res.phase1.any():
        cut = np.flatnonzero(res.phase1)[-1] + 1.5
        ax.axvline(cut, color=INK_3, lw=1, ls=":")
        ytop = ax.get_ylim()[1]
        ax.text(cut - 0.3, ytop, "Phase I  ", ha="right", va="top", fontsize=8, color=INK_2)
        ax.text(cut + 0.3, ytop, "  Phase II", ha="left", va="top", fontsize=8, color=INK_2)

    # limit labels at the right edge
    xr = x[-1] + 0.6
    labs = [("UCL", res.ucl[-1]), ("CL", res.center[-1])]
    if res.kind not in ("t2",):
        labs.append(("LCL", res.lcl[-1]))
    for name, val in labs:
        ax.text(xr, val, f" {name} {val:.4g}", va="center", fontsize=8, color=INK_2, clip_on=False)

    ax.set_xlim(0.3, x[-1] + 0.7)
    n = len(x)
    step = max(1, int(np.ceil(n / 15)))
    ax.set_xticks(x[::step])
    if xtick_labels:
        lab = [str(v)[:10] for v in res.labels]
        ax.set_xticklabels(lab[::step], rotation=0 if max(len(s) for s in lab) < 6 else 30,
                           ha="center" if max(len(s) for s in lab) < 6 else "right")
    ax.set_ylabel(ylabel or res.name, color=INK_2, fontsize=10)
    ax.set_title(title or f"{res.name} chart", loc="left", color=INK, fontsize=11, fontweight="bold")
    return ax


def plot_pair(top, bottom, *, title: str | None = None, figsize=(10, 6)):
    """Stack a location chart above its dispersion chart (X̄-R, X̄-S, I-MR)."""
    import matplotlib.pyplot as plt

    fig, (a1, a2) = plt.subplots(2, 1, figsize=figsize, sharex=True, gridspec_kw=dict(hspace=0.25))
    plot_chart(top, a1, title=title or f"{top.name}-{bottom.name} chart", xtick_labels=False)
    plot_chart(bottom, a2, title=f"{bottom.name}", show_zones=False)
    fig.subplots_adjust(right=0.88)
    return fig


def plot_capability(cap, ax=None, *, bins: int | None = None):
    import matplotlib.pyplot as plt
    from scipy import stats

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))
    _style(ax)
    x = cap.data
    bins = bins or int(np.clip(np.sqrt(x.size) * 1.5, 8, 40))
    ax.hist(x, bins=bins, density=True, color=SERIES, alpha=0.35, edgecolor=SURFACE, lw=1)
    lo = min([x.min()] + [v for v in (cap.lsl,) if v is not None])
    hi = max([x.max()] + [v for v in (cap.usl,) if v is not None])
    pad = (hi - lo) * 0.15
    g = np.linspace(lo - pad, hi + pad, 400)
    ax.plot(g, stats.norm.pdf(g, cap.mean, cap.sigma_within), color=SERIES, lw=2, label="within (short-term)")
    ax.plot(g, stats.norm.pdf(g, cap.mean, cap.sigma_overall), color=SERIES_2, lw=2, ls=(0, (5, 3)),
            label="overall (long-term)")
    ymax = ax.get_ylim()[1]
    for name, v in (("LSL", cap.lsl), ("Target", cap.target), ("USL", cap.usl)):
        if v is not None:
            ax.axvline(v, color=CRITICAL if name != "Target" else INK_2, lw=1.5,
                       ls="-" if name != "Target" else ":")
            ax.text(v, ymax * 0.98, f" {name}\n {v:g}", va="top", fontsize=8,
                    color=CRITICAL if name != "Target" else INK_2)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2,
              labelcolor=INK_2)
    i = cap.indices
    parts = [f"{k} {i[k]:.2f}" for k in ("Cp", "Cpk", "Pp", "Ppk") if k in i]
    ax.set_title("Process capability   " + "   ".join(parts), loc="left", color=INK, fontsize=11,
                 fontweight="bold")
    return ax


def plot_pareto(table, ax=None, *, title: str = "Pareto chart"):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 4.2))
    _style(ax)
    cats = [str(c) for c in table.index]
    x = np.arange(len(cats))
    colors = [SERIES if v else "#b7d3f6" for v in table["vital_few"]]
    ax.bar(x, table["count"], color=colors, width=0.7)
    for xi, c in zip(x, table["count"]):
        ax.text(xi, c, f"{c:,.0f}", ha="center", va="bottom", fontsize=8, color=INK_2)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("count", color=INK_2)
    ax2 = ax.twinx()
    ax2.plot(x, table["cumulative_share"], color=INK, lw=1.5, marker="o", ms=4)
    ax2.axhline(0.8, color=INK_3, lw=1, ls=":")
    ax2.set_ylim(0, 1.05)
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax2.tick_params(colors=INK_2, labelsize=9)
    for side in ("top",):
        ax2.spines[side].set_visible(False)
    ax2.spines["right"].set_color(INK_3)
    ax2.set_ylabel("cumulative share", color=INK_2)
    ax.set_title(title + "  (dark bars = vital few to 80 %)", loc="left", color=INK, fontsize=11,
                 fontweight="bold")
    return ax
