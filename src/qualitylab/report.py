"""A one-page decision brief (self-contained HTML) to forward to colleagues."""
from __future__ import annotations

import base64
import html
from datetime import date

import numpy as np
import pandas as pd

from .decide import Decision, _money, explain


def _md_inline(s: str) -> str:
    s = html.escape(s)
    out, bold, ital = [], False, False
    i = 0
    while i < len(s):
        if s.startswith("**", i):
            out.append("</strong>" if bold else "<strong>")
            bold = not bold
            i += 2
        elif s[i] == "*":
            out.append("</em>" if ital else "<em>")
            ital = not ital
            i += 1
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _img(png: bytes, alt: str) -> str:
    return f'<img alt="{html.escape(alt)}" src="data:image/png;base64,{base64.b64encode(png).decode()}">'


def build_brief(decision: Decision, *, title: str, figures: dict[str, bytes] | None = None,
                sensitivity: pd.DataFrame | None = None, aim: dict | None = None,
                investments: pd.DataFrame | None = None) -> str:
    d = decision
    p = d.process
    cur, rec = d.current.summary(), d.simplest.summary()
    figures = figures or {}

    def row(label, a, b, fmt):
        return f"<tr><td>{label}</td><td>{fmt(a)}</td><td><strong>{fmt(b)}</strong></td></tr>"

    money = _money
    rows = "".join([
        row("Expected cost per year", cur["annual_cost"], rec["annual_cost"], money),
        row("Range in 8 of 10 years", (cur["cost_p10"], cur["cost_p90"]), (rec["cost_p10"], rec["cost_p90"]),
            lambda t: f"{money(t[0])} – {money(t[1])}"),
        row("Hours until a problem is fixed", cur["hours_to_fix"], rec["hours_to_fix"], lambda x: f"{x:.1f} h"),
        row("Defects reaching customers (per million)", cur["escapes_ppm"], rec["escapes_ppm"], lambda x: f"{x:,.0f}"),
        row("False alarms per week", cur["false_alarms_per_week"], rec["false_alarms_per_week"], lambda x: f"{x:.1f}"),
        row("Units tested per year", cur["units_tested_per_year"], rec["units_tested_per_year"], lambda x: f"{x:,.0f}"),
    ])
    bullets = "".join(f"<li>{_md_inline(m)}</li>" for m in explain(d))
    fm_rows = "".join(
        f"<tr><td>{html.escape(f.name)}</td><td>every {f.every_hours / p.hours_per_day:.1f} operating days</td></tr>"
        for f in p.failure_modes)
    sens_html = ""
    if sensitivity is not None and len(sensitivity):
        holds = sensitivity[["recommended_still_best_low", "recommended_still_best_high"]].all(axis=1)
        items = "".join(
            f"<li>{html.escape(r['input'])}: saving {money(r['savings_low'])} at half, {money(r['savings_high'])} "
            f"at 1.5×{'' if h else ' (at one end another plan would be more than 10 % cheaper)'}</li>"
            for (_, r), h in zip(sensitivity.iterrows(), holds))
        sens_html = f"<h2>Does the answer hold up?</h2><ul>{items}</ul>"
    aim_html = ""
    if aim is not None and aim["annual_savings"] > 0:
        aim_html = (f"<h2>Process aim</h2><p>Moving the average from {aim['current_aim']:.4g} to "
                    f"{aim['best_aim']:.4g} {html.escape(p.unit_label)} would cut overfill and out-of-spec costs by "
                    f"about <strong>{money(aim['annual_savings'])} a year</strong> (in normal operation).</p>")
    inv_html = ""
    if investments is not None and len(investments) > 1:
        r = "".join(
            f"<tr><td>{html.escape(str(x['investment']))}</td><td>{money(x['investment_cost'])}</td>"
            f"<td>{money(x['net_benefit'])}</td><td>{'' if not np.isfinite(x['payback_months']) else f'{x.payback_months:.0f} mo'}</td></tr>"
            for _, x in investments.iloc[1:].iterrows())
        inv_html = ("<h2>Investments</h2><table><tr><th>Option</th><th>Cost / yr</th><th>Net benefit / yr</th>"
                    f"<th>Payback</th></tr>{r}</table>")
    figs = "".join(f"<figure>{_img(b, k)}<figcaption>{html.escape(k)}</figcaption></figure>" for k, b in figures.items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}: decision brief</title>
<style>
:root{{--ink:#0b0b0b;--ink2:#52514e;--line:#e3e2de;--bg:#fcfcfb;--accent:#2a78d6}}
body{{font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);
background:var(--bg);max-width:860px;margin:32px auto;padding:0 16px}}
h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:18px;margin:28px 0 8px}} .sub{{color:var(--ink2);margin:0 0 20px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}} td,th{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}}
th{{color:var(--ink2);font-weight:600}} figure{{margin:18px 0}} img{{max-width:100%;height:auto}}
figcaption{{color:var(--ink2);font-size:13px}} .box{{border-left:4px solid var(--accent);padding:4px 14px;background:#f3f7fd}}
footer{{color:var(--ink2);font-size:12px;margin-top:32px}}
@media print{{body{{margin:0}}}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="sub">Decision brief · {date.today():%B %d, %Y} · {html.escape(p.name)}</p>
<div class="box"><ul>{bullets}</ul></div>
<h2>Today vs. recommended</h2>
<table><tr><th></th><th>Today</th><th>Recommended</th></tr>{rows}</table>
<p><strong>Today:</strong> {html.escape(d.current.policy.describe(p))}.<br>
<strong>Recommended:</strong> {html.escape(d.simplest.policy.describe(p))}.</p>
{figs}{sens_html}{aim_html}{inv_html}
<h2>Assumptions</h2>
<p>{p.units_per_hour:,.0f} units/hour, {p.hours_per_day:g} h/day, {p.days_per_year:g} days/year.
Problems modeled:</p><table>{fm_rows}</table>
<p>Without monitoring, problems are noticed after {('never' if p.notice_after_hours is None else f'{p.notice_after_hours:g} h')}.
Costs per event: defect reaching a customer {money(p.costs.escape)}, scrap/rework {money(p.costs.internal)},
false alarm {money(p.costs.false_alarm)}, fixing a real problem {money(p.costs.repair)}, testing a unit {money(p.costs.per_unit_tested)}.
Results come from a Monte Carlo simulation of many operating years; they are estimates, as good as these inputs.</p>
<footer>Generated with QualityLab.</footer>
</body></html>"""
