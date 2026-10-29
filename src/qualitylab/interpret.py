"""Plain-language explanations of chart results, for students and managers."""
from __future__ import annotations

import numpy as np

from .result import ChartResult
from .rules import PLAIN_LANGUAGE, RULE_DESCRIPTIONS


def _fmt(labels, idx, limit=8):
    names = [str(labels[i]) for i in idx]
    if len(names) > limit:
        return ", ".join(names[:limit]) + f" … (+{len(names) - limit} more)"
    return ", ".join(names)


def explain(res: ChartResult, partner: ChartResult | None = None) -> list[str]:
    """Return a list of short paragraphs interpreting a chart (and its dispersion partner)."""
    out: list[str] = []
    p1, p2 = res.phase1, ~res.phase1
    n_p1 = int(p1.sum())
    if p2.any():
        out.append(f"Limits were estimated from the first {n_p1} points (Phase I) and then held fixed "
                   f"to monitor the remaining {int(p2.sum())} points (Phase II).")
    else:
        out.append(f"Limits were estimated from all {n_p1} points (a retrospective Phase I study).")
    if res.excluded.any():
        out.append(f"Point(s) {_fmt(res.labels, np.flatnonzero(res.excluded))} were left out when estimating "
                   "the limits. Only do this when you have found (and removed) the special cause behind them.")

    charts = [res] + ([partner] if partner is not None else [])
    any_signal = False
    for ch in charts:
        for phase_name, mask in (("Phase I", p1), ("Phase II", p2)):
            for rule in sorted(ch.violations):
                pos = ch.violations[rule]
                pos = pos[mask[pos]]
                if pos.size == 0:
                    continue
                any_signal = True
                where = f" in {phase_name}" if p2.any() else ""
                out.append(f"**{ch.name} chart, rule {rule}** ({RULE_DESCRIPTIONS[rule]}){where}: "
                           f"point(s) {_fmt(ch.labels, pos)}. {PLAIN_LANGUAGE[rule]}")

    if partner is not None and partner.violations.get(1, np.array([])).size:
        out.append(f"The {partner.name} chart shows unusual *variation*. Fix that first: the "
                   f"{res.name} chart's limits are computed from the average variation, so they are "
                   "unreliable while the variation itself is out of control.")
    if not any_signal:
        out.append("No signals: the process is behaving consistently (common-cause variation only). "
                   "This does **not** mean it meets customer specifications; check capability for that.")
    elif p1.all():
        out.append("Next step: investigate each signal. If you find and remove its cause, exclude those "
                   "points and recompute the limits (the *revised limits* option). Then use the revised limits "
                   "to monitor future data.")
    if res.kind == "ewma":
        out.append(f"EWMA with λ = {res.params['lam']}: each plotted value is a weighted average that gives "
                   f"{res.params['lam']:.0%} weight to the newest observation. It reacts to small, sustained "
                   "shifts sooner than an individuals chart.")
    if res.kind == "cusum":
        est = res.extra["shift_estimate"]
        first = res.first_signal()
        if first is not None:
            n_up, n_dn = res.extra["N_plus"][first], res.extra["N_minus"][first]
            direction, nn = ("up", n_up) if res.statistic[first] > res.params["H"] else ("down", n_dn)
            out.append(f"The CUSUM first signalled at point {res.labels[first]} (shift {direction}). "
                       f"Counting back, the shift most likely began about {nn} points earlier, near point "
                       f"{res.labels[max(0, first - nn + 1)]}; the new mean is estimated at {est[first]:.4g} "
                       f"(target {res.params['mu']:.4g}).")
    if res.name in ("p", "u") and res.params.get("sigma_z", 1.0) > 1.5:
        out.append(f"The points vary about {res.params['sigma_z']:.1f}× more than the "
                   f"{'binomial' if res.name == 'p' else 'Poisson'} model behind these limits allows "
                   "(overdispersion, typical with very large samples). The limits are probably too narrow; "
                   "try the Laney version.")
    if res.name in ("p'", "u'"):
        out.append(f"Laney adjustment: limits widened by a factor of {res.params['sigma_z']:.2f} to reflect "
                   "real period-to-period variation that the basic model ignores.")
    return out
