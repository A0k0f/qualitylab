"""Decision Studio: describe a process, simulate plans, get a recommendation."""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from qualitylab import decision_plots as dp
from qualitylab.decide import (
    Investment,
    _money,
    aim_recommendation,
    calibrate,
    compare_investments,
    cost_breakdown,
    explain,
    optimize,
    sensitivity,
)
from qualitylab.report import build_brief
from qualitylab.scenarios import templates
from qualitylab.simulate import Costs, FailureMode, Policy, Process, trace

CHECK_LABELS = {
    "none": "No routine checks",
    "spec": "Check units; act if any is out of spec / defective",
    "shewhart": "Control chart (Shewhart)",
    "ewma": "EWMA chart",
    "cusum": "CUSUM chart",
    "adjust": "Re-aim the process after every check (no chart)",
}
FINAL_LABELS = {"none": "Nothing: ship as made", "screen": "100 % inspection", "lots": "Lot sampling (accept / reject lots)"}


# ---------------------------------------------------------------------------
# scenario state
# ---------------------------------------------------------------------------

def _blank(kind: str) -> dict:
    if kind == "measurement":
        proc = Process("My process", "measurement", units_per_hour=100, unit_label="units", target=10.0, mean=10.0,
                       sigma=0.1, lsl=9.7, usl=10.3,
                       failure_modes=[FailureMode("Something shifts the average", every_hours=160, shift=0.2)],
                       notice_after_hours=16, costs=Costs(escape=10, internal=2, per_unit_tested=0.5, per_check=2,
                                                          false_alarm=50, repair=100, per_unit_screened=0.2))
    else:
        proc = Process("My process", "pass_fail", units_per_hour=100, defect_rate=0.01,
                       failure_modes=[FailureMode("Something raises the error rate", every_hours=160, rate_factor=3)],
                       notice_after_hours=24, costs=Costs(escape=20, internal=2, per_unit_tested=0.5, per_check=2,
                                                          false_alarm=50, repair=100, per_unit_screened=0.3))
    return dict(title="Blank scenario", pain="", industry="", process=proc.to_dict(),
                current=Policy("none").__dict__, investments=[], constraints={})


def _from_template(t) -> dict:
    return dict(title=t.title, pain=t.pain, industry=t.industry, process=t.process.to_dict(),
                current=dict(t.current.__dict__), investments=[i.__dict__ for i in t.investments],
                constraints=dict(max_escape_ppm=t.max_escape_ppm, max_false_alarms_per_week=t.max_false_alarms_per_week))


TPL = templates()
choices = list(TPL) + ["blank_measurement", "blank_pass_fail"]
names = {k: f"{t.title} · {t.industry}" for k, t in TPL.items()}
names |= {"blank_measurement": "Blank: measured characteristic", "blank_pass_fail": "Blank: pass / fail (errors)"}

st.sidebar.markdown("**Scenario**")
choice = st.sidebar.selectbox("Start from", choices, format_func=names.get, key="ds_choice")
up = st.sidebar.file_uploader("…or open a saved scenario (.json)", type=["json"], key="ds_upload")

if up is not None:
    raw = up.getvalue()
    sig = "upload:" + hashlib.sha1(raw).hexdigest()
else:
    sig = "tpl:" + choice
if st.session_state.get("ds_sig") != sig:
    try:
        if up is not None:
            base = json.loads(raw)
            Process.from_dict(base["process"]).validate()
        elif choice.startswith("blank_"):
            base = _blank(choice.removeprefix("blank_"))
        else:
            base = _from_template(TPL[choice])
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not open that scenario: {e}")
        st.stop()
    st.session_state.ds_sig = sig
    st.session_state.ds_base = base
    st.session_state.ds_ver = st.session_state.get("ds_ver", 0) + 1
    for k in ("ds_result", "ds_sens", "ds_inv"):
        st.session_state.pop(k, None)

base = st.session_state.ds_base
V = st.session_state.ds_ver
bp = Process.from_dict(base["process"])
bc = Policy(**base["current"])
meas = bp.kind == "measurement"


def esc(text: str) -> str:
    """Streamlit markdown treats $...$ as math; escape dollar signs."""
    return text.replace("$", r"\$")


def K(name: str) -> str:
    return f"ds{V}:{name}"


# ---------------------------------------------------------------------------
# header
# ---------------------------------------------------------------------------

st.title("🧭 Decision Studio")
st.caption("Describe your process, then let the simulator find the cheapest way to keep it under control.")
if base.get("pain"):
    st.info(esc(f"**The problem:** “{base['pain']}”  \n{bp.description}"))

# ---------------------------------------------------------------------------
# step 1: describe the process
# ---------------------------------------------------------------------------

st.header("1 · Describe your process")
t_basic, t_quality, t_wrong, t_money, t_today, t_limits = st.tabs(
    ["Volume", "Quality", "What goes wrong", "Costs", "Today's approach", "Your limits"])

with t_basic:
    c1, c2, c3, c4 = st.columns(4)
    pname = c1.text_input("Process name", bp.name, key=K("name"))
    uph = c2.number_input("Units per hour", min_value=0.01, value=float(bp.units_per_hour), key=K("uph"),
                          help="Bottles, parts, orders, invoices… whatever you make or process.")
    hpd = c3.number_input("Operating hours per day", min_value=0.5, max_value=24.0, value=float(bp.hours_per_day),
                          key=K("hpd"))
    dpy = c4.number_input("Operating days per year", min_value=1.0, max_value=366.0, value=float(bp.days_per_year),
                          key=K("dpy"))
    st.caption(f"That is **{uph * hpd * dpy:,.0f} units a year**. Type of quality measure: "
               f"**{'a measured value with spec limits' if meas else 'pass / fail (each unit is right or wrong)'}** "
               "(pick a different starting scenario to change this).")

with t_quality:
    if meas:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        unit = c1.text_input("Unit", bp.unit_label, key=K("unit"))
        lsl_on = c2.checkbox("Lower spec", bp.lsl is not None, key=K("lslon"))
        lsl = c2.number_input("LSL", value=float(bp.lsl if bp.lsl is not None else bp.mean - 4 * bp.sigma),
                              format="%.4f", disabled=not lsl_on, key=K("lsl"))
        usl_on = c3.checkbox("Upper spec", bp.usl is not None, key=K("uslon"))
        usl = c3.number_input("USL", value=float(bp.usl if bp.usl is not None else bp.mean + 4 * bp.sigma),
                              format="%.4f", disabled=not usl_on, key=K("usl"))
        target = c4.number_input("Target / label value", value=float(bp.target), format="%.4f", key=K("target"),
                                 help="For filling: the declared content. Overfill is measured from here.")
        mean = c5.number_input("Where the process runs (average)", value=float(bp.mean), format="%.4f", key=K("mean"))
        sigma = c6.number_input("Typical variation (σ)", min_value=1e-9, value=float(bp.sigma), format="%.4f",
                                key=K("sigma"),
                                help="Standard deviation in normal operation: about 2 in 3 units fall within ± σ of "
                                     "the average. Estimate it from your data below.")
    else:
        c1, _ = st.columns([1, 3])
        rate_pct = c1.number_input("Normal error rate (%)", min_value=0.001, max_value=99.0,
                                   value=float(bp.defect_rate * 100), format="%.3f", key=K("rate"),
                                   help="Share of units that are wrong when nothing unusual is going on.")
    with st.expander("Estimate these from my historical data"):
        f = st.file_uploader("CSV or Excel file", type=["csv", "xlsx"], key=K("calfile"))
        if f is not None:
            dfc = pd.read_excel(f) if f.name.endswith("xlsx") else pd.read_csv(f)
            nums = [c for c in dfc.columns if pd.api.types.is_numeric_dtype(dfc[c])]
            hrs = st.number_input("Hours between observations (optional, to estimate how often problems occur)",
                                  min_value=0.0, value=0.0, key=K("calhrs"))
            try:
                if meas:
                    cols = st.multiselect("Measurement column(s): several = subgroups", nums, default=nums[:1],
                                          key=K("calcols"))
                    est = calibrate(dfc[cols] if len(cols) > 1 else dfc[cols[0]], hours_between=hrs or None)
                    st.write(f"Average **{est['mean']:.4g}**, short-term σ **{est['sigma']:.4g}**, "
                             f"{est['episodes']} unusual episode(s) in {est['points']} points.")
                else:
                    dcol = st.selectbox("Defectives column", nums, key=K("caldef"))
                    ncol = st.selectbox("Sample size column", [c for c in nums if c != dcol], key=K("caln"))
                    est = calibrate(defectives=dfc[dcol], sizes=dfc[ncol], hours_between=hrs or None)
                    st.write(f"Normal error rate **{est['defect_rate']:.3%}**, {est['episodes']} unusual "
                             f"episode(s) in {est['points']} periods.")
                if "problem_every_hours" in est:
                    st.write(f"That suggests a problem roughly every **{est['problem_every_hours']:,.0f} operating "
                             "hours**; use it as a sanity check for the *What goes wrong* tab.")

                def _apply(est=est):
                    if meas:
                        st.session_state[K("mean")] = float(est["mean"])
                        st.session_state[K("sigma")] = float(est["sigma"])
                    else:
                        st.session_state[K("rate")] = float(est["defect_rate"] * 100)

                st.button("Use these values", on_click=_apply, key=K("calapply"))
            except Exception as e:  # noqa: BLE001
                st.warning(f"Could not estimate from these columns: {e}")

with t_wrong:
    st.write("List the things that occasionally go wrong. A problem stays until someone finds and fixes it.")
    if meas:
        fm_df = pd.DataFrame([{
            "Problem": f.name, "Happens every (operating days)": round(f.every_hours / bp.hours_per_day, 2),
            f"Average moves by ({bp.unit_label or 'units'})": f.shift,
            "Then keeps drifting per hour": f.drift_per_hour, "Variation ×": f.sigma_factor} for f in bp.failure_modes])
        cfg = {"Variation ×": st.column_config.NumberColumn(min_value=0.1, help="2 = twice as much spread"),
               "Happens every (operating days)": st.column_config.NumberColumn(min_value=0.01)}
    else:
        fm_df = pd.DataFrame([{
            "Problem": f.name, "Happens every (operating days)": round(f.every_hours / bp.hours_per_day, 2),
            "Error rate ×": f.rate_factor, "Gets worse by (× per hour)": f.drift_per_hour} for f in bp.failure_modes])
        cfg = {"Error rate ×": st.column_config.NumberColumn(min_value=0.1, help="3 = three times the normal rate"),
               "Happens every (operating days)": st.column_config.NumberColumn(min_value=0.01)}
    fm_edit = st.data_editor(fm_df, num_rows="dynamic", width="stretch", column_config=cfg, key=K("fm"))
    c1, c2 = st.columns([1, 2])
    noticed = c1.checkbox("Without checks, problems still get noticed eventually", bp.notice_after_hours is not None,
                          key=K("noticed"),
                          help="Customer complaints, an end-of-day lab test, month-end reconciliation…")
    notice_h = c2.number_input("…after about this many operating hours", min_value=0.1,
                               value=float(bp.notice_after_hours or 24), disabled=not noticed, key=K("notice"))

with t_money:
    c = bp.costs
    st.write("Rough numbers are fine; the *Robustness* check shows which ones matter.")
    c1, c2, c3 = st.columns(3)
    escape = c1.number_input("A defect reaching a customer ($)", min_value=0.0, value=float(c.escape), key=K("escape"),
                             help="Returns, credits, warranty, chargebacks, lost goodwill: per defective unit.")
    internal = c1.number_input("A defect caught in-house ($)", min_value=0.0, value=float(c.internal), key=K("internal"),
                               help="Scrap or rework per defective unit found before shipping.")
    giveaway = 0.0
    if meas:
        giveaway = c1.number_input(f"Overfill: per {bp.unit_label or 'unit'} above target, per unit made ($)",
                                   min_value=0.0, value=float(c.giveaway), format="%.4f", key=K("giveaway"),
                                   help="Product given away. Leave 0 if being above target costs nothing.")
    per_unit = c2.number_input("Testing / measuring one unit ($)", min_value=0.0, value=float(c.per_unit_tested),
                               format="%.3f", key=K("put"))
    per_check = c2.number_input("Fixed cost of each check ($)", min_value=0.0, value=float(c.per_check), key=K("pc"),
                                help="Walking over, recording, paperwork.")
    screen = c2.number_input("100 % inspection, per unit ($)", min_value=0.0, value=float(c.per_unit_screened),
                             format="%.3f", key=K("scr"))
    false_alarm = c3.number_input("A false alarm ($)", min_value=0.0, value=float(c.false_alarm), key=K("fa"),
                                  help="Stopping to investigate when nothing is wrong: downtime plus people's time.")
    repair = c3.number_input("Fixing a real problem ($)", min_value=0.0, value=float(c.repair), key=K("rep"))
    eff = c3.slider("100 % inspection catches this share of defects", 0.0, 1.0, float(bp.inspection_effectiveness),
                    0.01, key=K("eff"))

with t_today:
    st.write("How the process is watched today. The simulator compares everything against this.")
    checks = [k for k in CHECK_LABELS if meas or k != "adjust"]
    c1, c2, c3 = st.columns([2, 1, 1])
    cur_check = c1.selectbox("Routine checks", checks, index=checks.index(bc.check), format_func=CHECK_LABELS.get,
                             key=K("ccheck"))
    cur_n = c2.number_input("Units per check", min_value=1, value=int(bc.n), key=K("cn"),
                            disabled=cur_check == "none")
    cur_every = c3.number_input("Every (operating hours)", min_value=0.05, value=float(bc.every_hours), key=K("cevery"),
                                disabled=cur_check == "none")
    cur_L, cur_lam, cur_h = bc.L, bc.lam, bc.h
    if cur_check in ("shewhart", "ewma", "cusum"):
        with st.expander("Chart settings"):
            if cur_check in ("shewhart", "ewma"):
                cur_L = st.number_input("Limit width L (σ)", 1.0, 5.0, float(bc.L), 0.1, key=K("cL"))
            if cur_check == "ewma":
                cur_lam = st.number_input("λ", 0.01, 1.0, float(bc.lam), 0.05, key=K("clam"))
            if cur_check == "cusum":
                cur_h = st.number_input("h", 1.0, 10.0, float(bc.h), 0.5, key=K("ch"))
    finals = list(FINAL_LABELS)
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    cur_final = c1.selectbox("Before shipping", finals, index=finals.index(bc.final), format_func=FINAL_LABELS.get,
                             key=K("cfinal"))
    lot_n = c2.number_input("Sample per lot", min_value=1, value=int(bc.lot_n), key=K("lotn"),
                            disabled=cur_final != "lots")
    lot_c = c3.number_input("Reject if defectives exceed", min_value=0, value=int(bc.lot_c), key=K("lotc"),
                            disabled=cur_final != "lots")
    lot_h = c4.number_input("Lot = output of (hours)", min_value=0.5, value=float(bp.lot_length), key=K("loth"),
                            disabled=cur_final != "lots", help="Also used when the simulator tries lot sampling.")

with t_limits:
    st.write("Optional. Plans that break a limit are never recommended.")
    lim = base.get("constraints") or {}
    c1, c2 = st.columns(2)
    esc_on = c1.checkbox("Limit defects reaching customers", lim.get("max_escape_ppm") is not None, key=K("eson"))
    esc_max = c1.number_input("…to at most (per million units)", min_value=0.0,
                              value=float(lim.get("max_escape_ppm") or 1000), disabled=not esc_on, key=K("esmax"))
    fa_on = c2.checkbox("Limit false alarms", lim.get("max_false_alarms_per_week") is not None, key=K("faon"),
                        help="Operators stop trusting a system that cries wolf.")
    fa_max = c2.number_input("…to at most (per week)", min_value=0.0,
                             value=float(lim.get("max_false_alarms_per_week") or 2), disabled=not fa_on, key=K("famax"))

# ---------------------------------------------------------------------------
# assemble the scenario from the widgets
# ---------------------------------------------------------------------------

def _fm_from_editor(df: pd.DataFrame) -> list[FailureMode]:
    out = []
    for _, r in df.iterrows():
        name = str(r.get("Problem") or "").strip()
        days = r.get("Happens every (operating days)")
        if not name or pd.isna(days) or days <= 0:
            continue
        def g(col, default, r=r):
            return float(r[col]) if col in r and not pd.isna(r[col]) else default

        if meas:
            out.append(FailureMode(name, every_hours=float(days) * hpd,
                                   shift=g(f"Average moves by ({bp.unit_label or 'units'})", 0.0),
                                   drift_per_hour=g("Then keeps drifting per hour", 0.0),
                                   sigma_factor=max(0.1, g("Variation ×", 1.0))))
        else:
            out.append(FailureMode(name, every_hours=float(days) * hpd, rate_factor=max(0.1, g("Error rate ×", 1.0)),
                                   drift_per_hour=g("Gets worse by (× per hour)", 0.0)))
    return out


try:
    kw = dict(name=pname, kind=bp.kind, units_per_hour=uph, hours_per_day=hpd, days_per_year=dpy,
              failure_modes=_fm_from_editor(fm_edit), notice_after_hours=notice_h if noticed else None,
              costs=Costs(escape=escape, internal=internal, per_unit_tested=per_unit, per_check=per_check,
                          false_alarm=false_alarm, repair=repair, per_unit_screened=screen, giveaway=giveaway),
              inspection_effectiveness=eff, lot_hours=lot_h, description=bp.description)
    if meas:
        kw.update(unit_label=unit, target=target, mean=mean, sigma=sigma, lsl=lsl if lsl_on else None,
                  usl=usl if usl_on else None)
    else:
        kw.update(defect_rate=rate_pct / 100)
    process = Process(**kw)
    process.validate()
    current = Policy(cur_check, n=int(cur_n), every_hours=float(cur_every), L=cur_L, lam=cur_lam, h=cur_h,
                     final=cur_final, lot_n=int(lot_n), lot_c=int(lot_c))
except ValueError as e:
    st.error(f"Please check your inputs: {e}")
    st.stop()

if not process.failure_modes:
    st.warning("No problems listed under *What goes wrong*. Without them, checks can only cost money.")

constraints = dict(max_escape_ppm=esc_max if esc_on else None, max_false_alarms_per_week=fa_max if fa_on else None)
scenario = dict(title=base.get("title", ""), pain=base.get("pain", ""), industry=base.get("industry", ""),
                process=process.to_dict(), current=dict(current.__dict__), investments=base.get("investments", []),
                constraints=constraints)
scenario_json = json.dumps(scenario, indent=2, default=float)
st.sidebar.download_button("💾 Save this scenario", scenario_json.encode(), file_name="qualitylab_scenario.json",
                           mime="application/json", help="Open it again later with the uploader above.")

# ---------------------------------------------------------------------------
# step 2: run
# ---------------------------------------------------------------------------

st.header("2 · Find the best plan")
c1, c2 = st.columns([1, 3])
depth = c1.radio("Search", ["Quick", "Thorough"], horizontal=True, key="ds_depth",
                 help="Thorough tries more chart settings and simulates more years (about 30 seconds).")
run_key = hashlib.sha1((scenario_json + depth).encode()).hexdigest()
go = c2.button("▶ Simulate and recommend", type="primary", width="stretch")

if go:
    bar = st.progress(0.0, text="Simulating plans…")
    try:
        d = optimize(process, current, **constraints, thorough=depth == "Thorough",
                     reps=600 if depth == "Thorough" else 400, years=0.25,
                     progress=lambda f: bar.progress(min(1.0, f), text=f"Simulating plans… {f:.0%}"))
    except ValueError as e:
        bar.empty()
        st.error(str(e))
        st.stop()
    bar.empty()
    st.session_state.ds_result = dict(key=run_key, decision=d)
    for k in ("ds_sens", "ds_inv"):
        st.session_state.pop(k, None)

res = st.session_state.get("ds_result")
if res is None:
    st.info("Adjust the inputs above (or keep the example values) and press **Simulate and recommend**. "
            "A quick search takes 5–15 seconds.")
    st.stop()
if res["key"] != run_key:
    st.warning("You changed inputs since the last run. The results below are for the previous inputs. "
               "Press **Simulate and recommend** to update.")
d = res["decision"]
P = d.process


def fig_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# step 3: results
# ---------------------------------------------------------------------------

st.header("3 · Results")
cur, rec = d.current.summary(), d.simplest.summary()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Expected annual saving", _money(cur["annual_cost"] - rec["annual_cost"]),
          help="Today's expected annual cost minus the recommended plan's.")
m2.metric("Problems fixed after", f"{rec['hours_to_fix']:.1f} h", f"{rec['hours_to_fix'] - cur['hours_to_fix']:+.1f} h",
          delta_color="inverse")
m3.metric("Defects reaching customers", f"{rec['escapes_ppm']:,.0f} ppm",
          f"{rec['escapes_ppm'] - cur['escapes_ppm']:+,.0f} ppm", delta_color="inverse")
m4.metric("False alarms per week", f"{rec['false_alarms_per_week']:.1f}",
          f"{rec['false_alarms_per_week'] - cur['false_alarms_per_week']:+.1f}", delta_color="inverse")
for m in explain(d):
    st.markdown("- " + esc(m))

def money_data():
    labels, evs = ["Today", "Recommended"], [d.current, d.simplest]
    if d.best.policy.short() != d.simplest.policy.short():
        labels.append("Cheapest found")
        evs.append(d.best)
    if d.no_checks.policy.short() != d.current.policy.short():
        labels.append("No routine checks")
        evs.append(d.no_checks)
    return labels, evs, cost_breakdown(*evs, labels=labels)


def money_fig(bd):
    fig, ax = plt.subplots(figsize=(10, 0.75 * len(bd) + 1.8))
    dp.plot_cost_breakdown(bd, ax)
    return fig


def trace_fig(hrs, seed):
    fig, axs = plt.subplots(2, 1, figsize=(10, 7.2), sharex=True)
    dp.plot_trace(trace(P, d.current.policy, hours=hrs, seed=int(seed)), P, axs[0], title="Today")
    dp.plot_trace(trace(P, d.simplest.policy, hours=hrs, seed=int(seed)), P, axs[1], title="Recommended")
    fig.subplots_adjust(hspace=0.75)
    return fig


def frontier_fig():
    fig, ax = plt.subplots(figsize=(10, 4.4))
    dp.plot_frontier(d.table, {"Today": d.current.policy.short(), "Recommended": d.simplest.policy.short()}, ax)
    return fig


def tornado_fig(table):
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(table) + 1.6))
    dp.plot_tornado(table, float(d.savings.mean()), ax)
    return fig


def aim_fig(a):
    fig, ax = plt.subplots(figsize=(10, 3.8))
    dp.plot_aim(a, P, ax)
    return fig


def show(fig):
    st.pyplot(fig, width="stretch")
    plt.close(fig)


has_aim = P.kind == "measurement" and P.costs.giveaway > 0
TRACE_HOURS = int(min(200, max(48, 6 * P.hours_per_day)))

tabs = ["Money", "See it happen", "All plans", "Robustness", "Investments"]
if has_aim:
    tabs.insert(4, "Process aim")
tabs.append("Download")
view = st.segmented_control("Show", tabs, default="Money", key="ds_view") or "Money"

if view == "Money":
    labels, evs, bd = money_data()
    show(money_fig(bd))
    tbl = bd.copy()
    tbl["Total"] = tbl.sum(axis=1)
    st.dataframe(tbl.loc[:, (tbl != 0).any(axis=0)].style.format(_money), width="stretch")
    st.caption("Plans: " + " · ".join(f"**{lab}**: {e.policy.describe(P)}" for lab, e in zip(labels, evs)))

if view == "See it happen":
    st.write("The same simulated stretch of operation under today's approach and under the recommendation. "
             "Shaded = a problem is present; ▲ = caught by a check; ✕ = false alarm; ◆ = noticed late.")
    st.caption("This is one random example to build intuition; luck plays a part in any single stretch. The "
               "numbers above average thousands of simulated years. Change *Example #* to see others.")
    c1, c2 = st.columns(2)
    hrs = c1.slider("Hours to show", 24, 400, TRACE_HOURS, 8, key="ds_trh")
    seed = c2.number_input("Example #", 1, 999, 7, key="ds_trs")
    show(trace_fig(hrs, seed))

if view == "All plans":
    show(frontier_fig())
    tab = d.table.copy()
    if not d.feasible:
        st.warning("No plan met every limit you set; showing all plans.")
    only_ok = st.checkbox("Only plans that meet my limits", value=d.feasible, key="ds_okonly")
    if only_ok:
        tab = tab[tab["meets_constraints"]]
    plans_view = tab[["policy", "annual_cost", "cost_p10", "cost_p90", "hours_to_fix", "escapes_ppm",
                      "false_alarms_per_week", "units_tested_per_year"]].head(25)
    plans_view.columns = ["Plan", "Expected cost / yr", "Low (P10)", "High (P90)", "Hours to fix", "Escapes (ppm)",
                    "False alarms / wk", "Units tested / yr"]
    st.dataframe(plans_view.style.format({"Expected cost / yr": _money, "Low (P10)": _money, "High (P90)": _money,
                                    "Hours to fix": "{:.1f}", "Escapes (ppm)": "{:,.0f}",
                                    "False alarms / wk": "{:.2f}", "Units tested / yr": "{:,.0f}"}),
                 width="stretch", hide_index=True)
    st.caption(f"{len(d.table):,} plans simulated. P10/P90: 8 in 10 simulated years fall between them.")

if view == "Robustness":
    st.write("Your inputs are estimates. This re-runs the key plans with each uncertain input at half and "
             "at 1.5× your value, and checks whether the recommendation still wins.")
    if st.button("Run robustness check", key="ds_sensbtn"):
        with st.spinner("Re-simulating under 10 alternative assumptions…"):
            st.session_state.ds_sens = dict(key=run_key, table=sensitivity(d))
    sens = st.session_state.get("ds_sens")
    if sens:
        s = sens["table"]
        show(tornado_fig(s))
        holds = s[["recommended_still_best_low", "recommended_still_best_high"]].all(axis=1)
        if holds.all():
            st.success("Under every alternative tested, the recommendation stays within 10 % of the best plan.")
        else:
            for _, r in s[~holds].iterrows():
                for tag, end in (("low", "half"), ("high", "1.5×")):
                    if not r[f"recommended_still_best_{tag}"]:
                        st.warning(esc(f"If **{r['input'].lower()}** is {end} your estimate, another plan "
                                   f"({r[f'best_plan_{tag}']}) would be {_money(r[f'regret_{tag}'])} a year "
                                   f"({r[f'regret_pct_{tag}']:.0%}) cheaper than the recommendation. "
                                   "Worth pinning that number down."))
            st.caption("Everywhere else, the recommendation stays within 10 % of the best plan.")
        neg = s[(s["savings_low"] < 0) | (s["savings_high"] < 0)]
        if len(neg):
            st.info("In some alternatives the switch would *cost* money: " + ", ".join(neg["input"].str.lower()) + ".")

if view == "Process aim":
    a = aim_recommendation(P)
    show(aim_fig(a))
    if a["annual_savings"] > 1:
        st.markdown(esc(f"Moving the average from **{a['current_aim']:.4g}** to **{a['best_aim']:.4g} {P.unit_label}** "
                    f"would save about **{_money(a['annual_savings'])} a year** in normal operation, with "
                    f"out-of-spec output going from {a['defect_rate_now'] * 1e6:,.0f} to "
                    f"{a['defect_rate_best'] * 1e6:,.0f} per million."))

        def _use_aim(v=a["best_aim"]):
            st.session_state[K("mean")] = float(round(v, 6))

        st.button("Use this aim in the scenario", on_click=_use_aim, key="ds_aimbtn",
                  help="Updates *Where the process runs* in step 1. Press Simulate again afterwards.")
    else:
        st.success("The process is already aimed at (or very near) the cheapest setting.")
    st.caption("This balances overfill against out-of-spec risk while the process is running normally. "
               "Problems that move the average are handled by the monitoring plan.")

if view == "Investments":
    st.write("What would it be worth to improve the process itself? Enter options with their yearly cost "
             "(e.g. depreciation + running cost). Factors below 1 mean *less*.")
    inv_df = pd.DataFrame(base.get("investments") or [{"name": "New option", "annual_cost": 10000.0}])
    for col, dflt in (("variation_factor", 1.0), ("defect_rate_factor", 1.0), ("frequency_factor", 1.0),
                      ("size_factor", 1.0), ("notice_factor", 1.0)):
        if col not in inv_df:
            inv_df[col] = dflt
    inv_df = inv_df[["name", "annual_cost", "variation_factor", "defect_rate_factor", "frequency_factor",
                     "size_factor", "notice_factor"]]
    inv_cfg = {"name": "Option", "annual_cost": st.column_config.NumberColumn("Cost per year ($)", min_value=0),
               "variation_factor": st.column_config.NumberColumn("Variation ×", help="measured processes"),
               "defect_rate_factor": st.column_config.NumberColumn("Normal error rate ×", help="pass/fail processes"),
               "frequency_factor": st.column_config.NumberColumn("Problems happen ×", help="0.5 = half as often"),
               "size_factor": st.column_config.NumberColumn("Problem size ×"),
               "notice_factor": st.column_config.NumberColumn("Time to notice ×")}
    inv_edit = st.data_editor(inv_df, num_rows="dynamic", width="stretch", column_config=inv_cfg,
                              key=f"ds{V}:inv")
    if st.button("Evaluate investments", key="ds_invbtn"):
        invs = [Investment(str(r["name"]), float(r["annual_cost"] or 0),
                           *[float(r[c]) if not pd.isna(r[c]) else 1.0 for c in
                             ("variation_factor", "defect_rate_factor", "frequency_factor", "size_factor",
                              "notice_factor")])
                for _, r in inv_edit.iterrows() if str(r["name"]).strip() and not pd.isna(r["name"])]
        with st.spinner("Simulating each option…"):
            st.session_state.ds_inv = compare_investments(d, invs)
    inv = st.session_state.get("ds_inv")
    if inv is not None:
        v = inv.copy()
        v.columns = ["Option", "Best plan with it", "Operating cost / yr", "Investment / yr", "Total / yr",
                     "Net benefit / yr", "Payback (months)"]
        st.dataframe(v.style.format({"Operating cost / yr": _money, "Investment / yr": _money, "Total / yr": _money,
                                     "Net benefit / yr": _money, "Payback (months)": "{:.0f}"}, na_rep="–"),
                     width="stretch", hide_index=True)
        best_row = inv.iloc[1:].sort_values("net_benefit", ascending=False).head(1)
        if len(best_row) and best_row["net_benefit"].iloc[0] > 0:
            st.success(esc(f"**{best_row['investment'].iloc[0]}** pays: net benefit "
                       f"{_money(best_row['net_benefit'].iloc[0])} a year after its own cost."))
        elif len(best_row):
            st.info("None of these options pays for itself under the current assumptions.")

if view == "Download":
    st.write("A one-page brief you can email or print, plus the full results.")
    sens = st.session_state.get("ds_sens")
    with st.spinner("Preparing the brief…"):
        _, _, bd = money_data()
        figs = {"Where the money goes": fig_png(money_fig(bd)),
                "A simulated stretch of operation": fig_png(trace_fig(TRACE_HOURS, 7)),
                "All plans tested": fig_png(frontier_fig())}
        if sens:
            figs["Robustness"] = fig_png(tornado_fig(sens["table"]))
        if has_aim:
            figs["Process aim"] = fig_png(aim_fig(aim_recommendation(P)))
        plt.close("all")
        brief = build_brief(d, title=base.get("title") or P.name, figures=figs,
                            sensitivity=sens["table"] if sens else None,
                            aim=aim_recommendation(P) if has_aim else None,
                            investments=st.session_state.get("ds_inv"))
    c1, c2, c3 = st.columns(3)
    c1.download_button("📄 Decision brief (HTML)", brief.encode(), file_name="decision_brief.html", mime="text/html",
                       help="Open in a browser; print to PDF if you need a PDF.")
    xbuf = io.BytesIO()
    with pd.ExcelWriter(xbuf, engine="openpyxl") as xw:
        d.table.drop(columns=["_i"]).to_excel(xw, sheet_name="All plans", index=False)
        bd.to_excel(xw, sheet_name="Cost breakdown")
        pd.DataFrame([{"field": k, "value": json.dumps(v, default=float) if isinstance(v, (dict, list)) else v}
                      for k, v in process.to_dict().items()]).to_excel(xw, sheet_name="Inputs", index=False)
    c2.download_button("📊 All results (Excel)", xbuf.getvalue(), file_name="decision_results.xlsx")
    c3.download_button("💾 Scenario (.json)", scenario_json.encode(), file_name="qualitylab_scenario.json",
                       mime="application/json")
    if not sens:
        st.caption("Tip: run the robustness check (and the investments) first to include them in the brief.")

with st.expander("How the simulation works and what it assumes"):
    st.markdown(
        "- Each plan is replayed over many simulated operating years (Monte Carlo). Problems strike at random at "
        "the rates you gave, last until a check catches them or they are noticed anyway, and push the process "
        "the way you described.\n"
        "- Every check, false alarm, fix, scrapped unit, inspected unit, unit of overfill and defect reaching a "
        "customer is costed. The plan with the lowest expected annual cost that meets your limits wins; the "
        "*recommended* plan is the simplest one within 5 % of it.\n"
        "- Assumptions: one problem at a time; fixes are immediate; control limits are set from normal operation; "
        "a rejected lot is screened but does not by itself trigger a fix of the process (so lot sampling is, if "
        "anything, slightly under-credited).\n"
        "- Treat results as well-founded estimates, not guarantees. The *Robustness* tab shows which inputs "
        "deserve a closer look.")
