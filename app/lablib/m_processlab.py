"""Process Lab: students design and run their own experiments on a process they define."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import streamlit as st

from qualitylab.learn import plots as LP
from qualitylab.learn import process_lab as PL

from .core import (
    ask_predictions,
    complete_mission,
    confidence,
    esc,
    fig_png,
    go,
    insight,
    lab,
    log,
    mstate,
    no_names_hint,
    predict_box,
    seed_for,
    start_mission,
)

M = "processlab"
GOALS = {
    "explore": "Just exploring",
    "fast": "Catch a change as quickly as possible",
    "few_alarms": "Avoid false alarms",
    "low_oos": "Keep out-of-spec output low",
    "cheap": "Find the cheapest way to watch this process",
    "own": "My own question (describe it below)",
}
# optional starting points; every number stays editable
EXAMPLES = {
    "Filling bottles (oz)": dict(name="Bottle filling", unit="oz", target=12.0, lsl=11.85, usl=12.15, sigma=0.04,
                                 n=4, units_per_sample=2000, cost_check=1.0, cost_investigation=250.0,
                                 cost_defect=3.0),
    "Call-center wait (minutes)": dict(name="Call wait time", unit="min", target=3.0, lsl=None, usl=6.0,
                                       sigma=0.8, n=1, units_per_sample=150, cost_check=0.5,
                                       cost_investigation=400.0, cost_defect=12.0),
    "Machined shaft (mm)": dict(name="Shaft diameter", unit="mm", target=25.0, lsl=24.95, usl=25.05, sigma=0.012,
                                n=5, units_per_sample=400, cost_check=4.0, cost_investigation=600.0,
                                cost_defect=80.0),
    "Invoice processing (hours)": dict(name="Invoice processing time", unit="h", target=24.0, lsl=None, usl=48.0,
                                       sigma=6.0, n=3, units_per_sample=300, cost_check=2.0,
                                       cost_investigation=300.0, cost_defect=15.0),
}
PROC_FIELDS = ["name", "unit", "target", "lsl", "usl", "sigma", "mean", "n", "samples", "baseline",
               "units_per_sample", "cost_check", "cost_investigation", "cost_defect"]


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

def _defaults() -> None:
    ss = st.session_state
    p = PL.Process()
    for f in PROC_FIELDS:
        ss.setdefault(f"pl_{f}", getattr(p, f))
    ss.setdefault("pl_has_lsl", True)
    ss.setdefault("pl_has_usl", True)
    ss.setdefault("pl_off_center", False)
    if ss.get("pl_mean") is None:
        ss["pl_mean"] = p.target
    mo = PL.Monitor()
    for f in ("chart", "rules", "limits_from", "react", "lam", "L_ewma", "k", "h"):
        ss.setdefault(f"pl_m_{f}", getattr(mo, f))
    ss.setdefault("pl_goal", "explore")


def _fill_example() -> None:
    ex = EXAMPLES.get(st.session_state.get("pl_example"))
    if not ex:
        return
    ss = st.session_state
    for k, v in ex.items():
        if k == "lsl":
            ss["pl_has_lsl"] = v is not None
            ss["pl_lsl"] = v if v is not None else ex["target"] - 3 * ex["sigma"]
        elif k == "usl":
            ss["pl_has_usl"] = v is not None
            ss["pl_usl"] = v if v is not None else ex["target"] + 3 * ex["sigma"]
        else:
            ss[f"pl_{k}"] = v
    ss["pl_mean"] = ex["target"]
    ss["pl_off_center"] = False
    log(M, "example", "decision", response=st.session_state["pl_example"])


def _experiment(s) -> PL.Experiment:
    ss = st.session_state
    proc = PL.Process(
        name=ss.pl_name.strip() or "My process", unit=ss.pl_unit.strip() or "units", target=float(ss.pl_target),
        lsl=float(ss.pl_lsl) if ss.pl_has_lsl else None, usl=float(ss.pl_usl) if ss.pl_has_usl else None,
        sigma=float(ss.pl_sigma), mean=float(ss.pl_mean) if ss.pl_off_center else None, n=int(ss.pl_n),
        samples=int(ss.pl_samples), baseline=int(ss.pl_baseline), units_per_sample=int(ss.pl_units_per_sample),
        cost_check=float(ss.pl_cost_check), cost_investigation=float(ss.pl_cost_investigation),
        cost_defect=float(ss.pl_cost_defect))
    changes = [PL.Change(kind=c["kind"], at=int(ss[f"pl_c_at_{c['id']}"]), size=float(ss[f"pl_c_size_{c['id']}"]))
               for c in s["changes"]]
    mon = PL.Monitor(chart=ss.pl_m_chart, rules=ss.pl_m_rules, limits_from=ss.pl_m_limits_from,
                     react=bool(ss.pl_m_react), lam=float(ss.pl_m_lam), L_ewma=float(ss.pl_m_L_ewma),
                     k=float(ss.pl_m_k), h=float(ss.pl_m_h))
    return PL.Experiment(proc, changes, mon)


@st.cache_data(max_entries=3000, show_spinner=False)
def _figure_png(exp_json: str, seed: int) -> bytes:
    exp = PL.Experiment.from_dict(json.loads(exp_json))
    return fig_png(LP.process_lab_figure(exp, PL.run(exp, seed)))


@st.cache_data(max_entries=500, show_spinner="Running your experiment many times…")
def _replicate(exp_json: str, reps: int, seed: int) -> dict:
    return PL.replicate(PL.Experiment.from_dict(json.loads(exp_json)), reps=reps, seed=seed)


def _summary(r: dict) -> dict:
    """The parts of a run worth storing (no raw arrays)."""
    return dict(changes=r["changes"], false_alarms=r["false_alarms"], quiet_samples=r["quiet_samples"],
                investigations=r["investigations"], oos_share=round(r["oos_share"], 6),
                oos_units=round(r["oos_units"], 2), costs={k: round(v, 2) for k, v in r["costs"].items()},
                capability={k: (None if v is None else round(v, 4)) for k, v in r["capability"].items()},
                signals=r["signals"], chart=r["chart_name"])


def _money(x: float) -> str:
    return f"${x:,.0f}".replace("$-", "−$")


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def _process_section() -> None:
    ss = st.session_state
    with st.container(border=True):
        st.markdown("#### 1 · Your process")
        st.caption("Any process with a measurable result: fill weight, wait time, delivery days, a dimension, "
                   "a processing time. Type your own numbers, or start from an example and change them.")
        st.selectbox("Start from an example (optional)", ["—"] + list(EXAMPLES), key="pl_example",
                     on_change=_fill_example)
        a, b = st.columns([2, 1])
        a.text_input("What is measured?", key="pl_name", max_chars=60)
        b.text_input("Unit", key="pl_unit", max_chars=12)
        c1, c2, c3 = st.columns(3)
        c1.number_input("Target", key="pl_target", format="%.4g")
        with c2:
            st.checkbox("Lower spec limit", key="pl_has_lsl")
            st.number_input("LSL", key="pl_lsl", format="%.4g", disabled=not ss.pl_has_lsl,
                            label_visibility="collapsed")
        with c3:
            st.checkbox("Upper spec limit", key="pl_has_usl")
            st.number_input("USL", key="pl_usl", format="%.4g", disabled=not ss.pl_has_usl,
                            label_visibility="collapsed")
        d1, d2 = st.columns(2)
        d1.number_input("Variation from unit to unit (standard deviation σ)", key="pl_sigma", min_value=1e-9,
                        format="%.4g", help="Common-cause variation: how much units differ when nothing is wrong.")
        with d2:
            st.checkbox("The process is not centered on target", key="pl_off_center")
            st.number_input("Actual average", key="pl_mean", format="%.4g", disabled=not ss.pl_off_center,
                            label_visibility="collapsed")
        e1, e2, e3 = st.columns(3)
        e1.slider("Units measured per sample (n)", 1, 25, key="pl_n")
        e2.slider("Number of samples", 30, 300, key="pl_samples", step=5)
        maxb = max(10, int(ss.pl_samples) - 5)
        if ss.pl_baseline > maxb:
            ss.pl_baseline = maxb
        e3.slider("Baseline samples (to set up the chart)", 10, maxb, key="pl_baseline")
        with st.expander("Volume and costs (used for the cost of each experiment)"):
            f1, f2, f3, f4 = st.columns(4)
            f1.number_input("Units made between samples", key="pl_units_per_sample", min_value=0, step=50)
            f2.number_input("Cost to measure one unit ($)", key="pl_cost_check", min_value=0.0)
            f3.number_input("Cost of one investigation ($)", key="pl_cost_investigation", min_value=0.0)
            f4.number_input("Cost of one bad unit reaching a customer ($)", key="pl_cost_defect", min_value=0.0)

        # live reading of the settings
        try:
            P = _experiment(mstate(M)).process
            if not P.problems():
                cap = PL.run(PL.Experiment(P, [], PL.Monitor(react=False)), 0, keep_data=False)
                tc = cap["capability"]
                txt = (f"With these settings, when nothing goes wrong: **Cpk = {tc['true_cpk']:.2f}**"
                       + (f", Cp = {tc['true_cp']:.2f}" if tc["true_cp"] is not None else "")
                       + f", and about **{cap['oos_share']:.3%}** of units fall outside the specification.")
                txt += (" That meets the common Cpk ≥ 1.33 requirement." if tc["true_cpk"] >= 1.33 else
                        " That is below the common Cpk ≥ 1.33 requirement: even a perfectly watched process "
                        "would ship defects.")
                st.caption(txt)
            else:
                for p in P.problems():
                    st.warning(p)
        except Exception:  # noqa: BLE001 - half-typed values; the run button validates properly
            pass


def _changes_section(s) -> None:
    ss = st.session_state
    with st.container(border=True):
        st.markdown("#### 2 · What happens to it")
        st.caption("Decide what goes wrong, when, and by how much. Leave the list empty to see how your chart "
                   "behaves when nothing goes wrong (a control experiment).")
        for c in list(s["changes"]):
            cid = c["id"]
            ss.setdefault(f"pl_c_at_{cid}", c["at"])
            ss.setdefault(f"pl_c_size_{cid}", c["size"])
            a, b, cc, d = st.columns([2.2, 1.2, 1.6, 0.5])
            a.markdown(f"**{PL.CHANGE_KINDS[c['kind']]}**")
            b.number_input("Starts at sample", 1, 500, key=f"pl_c_at_{cid}")
            label = {"shift": f"Shift size ({ss.pl_unit})", "drift": f"Drift per sample ({ss.pl_unit})",
                     "spread": "Spread multiplier (×σ)", "outlier": f"Outlier size ({ss.pl_unit})"}[c["kind"]]
            cc.number_input(label, key=f"pl_c_size_{cid}", format="%.4g")
            if d.button("✕", key=f"pl_c_del_{cid}", help="Remove this change"):
                s["changes"] = [x for x in s["changes"] if x["id"] != cid]
                st.rerun()
            size = float(ss[f"pl_c_size_{cid}"])
            if c["kind"] in ("shift", "outlier") and ss.pl_sigma > 0:
                a.caption(f"= {PL.sigma_note(size, float(ss.pl_sigma), int(ss.pl_n))}")
            elif c["kind"] == "drift" and ss.pl_sigma > 0:
                a.caption(f"= {size / float(ss.pl_sigma):+.2g}σ more every sample")
            if int(ss[f"pl_c_at_{cid}"]) <= int(ss.pl_baseline):
                a.caption("⚠️ starts during the baseline")
        a, b = st.columns([2, 3])
        kind = a.selectbox("Add a change", list(PL.CHANGE_KINDS), format_func=PL.CHANGE_KINDS.get,
                           key="pl_new_kind", label_visibility="collapsed")
        if b.button("➕ Add this change"):
            sig = float(ss.pl_sigma) if ss.pl_sigma > 0 else 1.0
            default = {"shift": sig, "drift": sig / 10, "spread": 1.5, "outlier": 4 * sig}[kind]
            at = min(int(ss.pl_samples), int(ss.pl_baseline) + 1 + 10 * len(s["changes"]) + 10)
            s["next_id"] = s.get("next_id", 0) + 1
            s["changes"].append(dict(id=s["next_id"], kind=kind, at=at, size=float(f"{default:.3g}")))
            st.rerun()


def _monitor_section() -> None:
    ss = st.session_state
    with st.container(border=True):
        st.markdown("#### 3 · How you watch it")
        n = int(ss.pl_n)
        st.radio("Chart", list(PL.CHART_TYPES), key="pl_m_chart", horizontal=True,
                 format_func=lambda k: {"shewhart": f"Shewhart ({PL.shewhart_name(n)})", "ewma": "EWMA",
                                        "cusum": "CUSUM"}[k])
        a, b = st.columns(2)
        a.radio("Signal rules", list(PL.RULE_SETS), key="pl_m_rules", format_func=PL.RULE_SETS.get,
                disabled=ss.pl_m_chart != "shewhart",
                help="Only for Shewhart charts. EWMA and CUSUM signal when their statistic crosses its limit.")
        b.radio("Control limits come from", ["baseline", "known"], key="pl_m_limits_from",
                format_func=lambda k: {"baseline": "the baseline samples (estimated)",
                                       "known": "the target and σ I entered (known)"}[k])
        b.toggle("React to signals (investigate, find and remove the cause)", key="pl_m_react")
        if ss.pl_m_chart != "shewhart":
            with st.expander("Chart settings"):
                c1, c2 = st.columns(2)
                if ss.pl_m_chart == "ewma":
                    c1.slider("λ (weight of the newest sample)", 0.05, 1.0, key="pl_m_lam", step=0.05)
                    c2.slider("L (width of the limits)", 2.0, 3.5, key="pl_m_L_ewma", step=0.01)
                else:
                    c1.slider("k (reference value, in σ of the plotted average)", 0.0, 1.5, key="pl_m_k", step=0.05)
                    c2.slider("h (decision interval)", 2.0, 8.0, key="pl_m_h", step=0.1)


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------

def _explain(exp: PL.Experiment, r: dict) -> list[str]:
    P, Mo = exp.process, exp.monitor
    out = []
    for c, o in zip(exp.changes, r["changes"]):
        desc = c.describe(P)
        z = abs(c.size) / P.sigma * np.sqrt(P.n)
        if o["in_baseline"]:
            out.append(f"The change where {desc} began **during the baseline**, so it went into the control limits: "
                       "the chart learned the problem as normal. Limits are only as good as the baseline data.")
        if o["detected"]:
            out.append(f"**Caught:** {desc}; your chart signaled at sample {o['signal_at']}, "
                       f"**{o['delay']} sample{'s' if o['delay'] != 1 else ''}** after it started.")
        else:
            why = ""
            if c.kind == "spread" and Mo.chart != "shewhart":
                why = " EWMA and CUSUM watch the average, not the spread; a Shewhart chart's R, S or MR chart watches spread."
            elif c.kind == "outlier" and Mo.chart != "shewhart":
                why = " EWMA and CUSUM average single points away; they are built for sustained shifts."
            elif c.kind in ("shift", "drift") and z < 1.5 and Mo.chart == "shewhart":
                why = (f" For a sample average this change is only about {z:.1f}σ, small for a Shewhart chart. "
                       "Try a larger sample, more run rules, or an EWMA or CUSUM chart.")
            out.append(f"**Missed:** {desc}, and your chart never signaled.{why}")
        if c.kind == "shift" and o["detected"] and Mo.chart == "shewhart" and Mo.rules == "limits":
            arl = PL.theoretical_shewhart(PL.Experiment(P, [c], Mo))["shifts"][0]["arl1"]
            out.append(f"In theory, a Shewhart chart with known limits needs **{arl:.1f} samples on average** to "
                       f"catch a shift this size. One run can be lucky or unlucky: use *Run it 200 times* to see the "
                       "typical delay.")
    q = r["quiet_samples"]
    if q:
        out.append(f"**False alarms:** {r['false_alarms']} signal{'s' if r['false_alarms'] != 1 else ''} in {q} "
                   "monitored samples when nothing was wrong."
                   + (" More run rules catch small changes sooner but also raise more false alarms."
                      if Mo.rules != "limits" and Mo.chart == "shewhart" else ""))
    cap = r["capability"]
    if cap["true_cpk"] < 1.33:
        out.append(f"Your process has Cpk = {cap['true_cpk']:.2f} even when nothing goes wrong, so it makes some "
                   "out-of-spec units no matter how well it is monitored. Monitoring finds changes; it does not "
                   "make a process capable.")
    if not Mo.react and exp.changes:
        out.append("Nobody reacted to signals, so every problem ran until the end of the experiment. Turn on "
                   "*React to signals* to see what fast detection is worth.")
    c = r["costs"]
    out.append(f"**Cost of this run:** {_money(c['total'])} = measuring {_money(c['checking'])} + investigations "
               f"{_money(c['investigations'])} + bad units reaching customers {_money(c['defects'])}.")
    return out


def _prediction_form(exp: PL.Experiment, k: int):
    """Returns the predictions dict, or None when predictions are not asked (control condition)."""
    if not ask_predictions():
        return None
    predict_box("Before you run it, say what you expect. You'll see how close you were.")
    pred: dict = {}
    if exp.changes:
        first = min(exp.changes, key=lambda c: c.at)
        st.markdown(f"About the first change ({esc(first.describe(exp.process))}):")
        a, b = st.columns(2)
        pred["detect"] = a.radio("Will your chart signal it?", ["Yes", "No"], index=None, key=f"pl_p_det_{k}",
                                 horizontal=True)
        pred["delay"] = b.number_input("If yes, how many samples after it starts?", 1, 500, value=None,
                                       key=f"pl_p_delay_{k}", placeholder="number of samples")
    a, b = st.columns(2)
    pred["false_alarms"] = a.number_input("How many false alarms (signals when nothing is wrong)?", 0, 500,
                                          value=None, key=f"pl_p_fa_{k}", placeholder="a whole number")
    pred["oos_pct"] = b.number_input("What share of units will be out of spec (%)?", 0.0, 100.0, value=None,
                                     step=0.1, key=f"pl_p_oos_{k}", placeholder="e.g. 0.5")
    pred["why"] = st.text_area("Why do you expect that? (optional)", key=f"pl_p_why_{k}", max_chars=800,
                               height=70)
    pred["confidence"] = confidence(f"pl_p_conf_{k}")
    return pred


def _score_predictions(pred: dict, exp: PL.Experiment, r: dict) -> dict:
    out: dict = {}
    if exp.changes:
        j = min(range(len(exp.changes)), key=lambda i: exp.changes[i].at)
        o = r["changes"][j]
        if pred.get("detect"):
            out["detect_correct"] = (pred["detect"] == "Yes") == o["detected"]
        if pred.get("detect") == "Yes" and pred.get("delay") is not None and o["detected"]:
            out["delay_abs_error"] = abs(int(pred["delay"]) - o["delay"])
            out["delay_log_error"] = round(abs(float(np.log(int(pred["delay"]) / o["delay"]))), 4)
    if pred.get("false_alarms") is not None:
        out["false_alarm_abs_error"] = abs(int(pred["false_alarms"]) - r["false_alarms"])
    if pred.get("oos_pct") is not None:
        out["oos_abs_error_pct_points"] = abs(float(pred["oos_pct"]) - 100 * r["oos_share"])
    return out


def _show_result(s, item: dict) -> None:
    exp = PL.Experiment.from_dict(item["exp"])
    r = PL.run(exp, item["seed"])
    st.markdown(f"### Experiment {item['k']}: results")
    st.image(_figure_png(json.dumps(item["exp"], sort_keys=True), item["seed"]), width="stretch")
    m1, m2, m3, m4 = st.columns(4)
    if r["changes"]:
        f = min(range(len(r["changes"])), key=lambda i: exp.changes[i].at)
        o = r["changes"][f]
        m1.metric("First change caught after", f"{o['delay']} samples" if o["detected"] else "never")
    else:
        m1.metric("Changes", "none (control run)")
    m2.metric("False alarms", r["false_alarms"])
    m3.metric("Out-of-spec units", f"{r['oos_share']:.2%}")
    m4.metric("Cost of this run", _money(r["costs"]["total"]))

    pred, sc = item.get("pred"), item.get("pred_score") or {}
    if pred:
        rows = []
        if "detect_correct" in sc or pred.get("detect"):
            f = min(range(len(r["changes"])), key=lambda i: exp.changes[i].at)
            o = r["changes"][f]
            rows.append(("Caught the first change?", pred.get("detect") or "–", "Yes" if o["detected"] else "No",
                         "✅" if sc.get("detect_correct") else "❌"))
            if pred.get("delay") is not None:
                rows.append(("Samples until caught", str(pred["delay"]), str(o["delay"]) if o["detected"] else "–",
                             f"off by {sc['delay_abs_error']}" if "delay_abs_error" in sc else "–"))
        if pred.get("false_alarms") is not None:
            rows.append(("False alarms", str(pred["false_alarms"]), str(r["false_alarms"]),
                         f"off by {sc['false_alarm_abs_error']}"))
        if pred.get("oos_pct") is not None:
            rows.append(("Out of spec", f"{pred['oos_pct']:.2f} %", f"{100 * r['oos_share']:.2f} %",
                         f"off by {sc['oos_abs_error_pct_points']:.2f} points"))
        if rows:
            st.markdown("**Your prediction vs. what happened**")
            st.dataframe(pd.DataFrame(rows, columns=["", "You predicted", "Actual", "How close"]), hide_index=True,
                         width="stretch")
    for line in _explain(exp, r):
        st.markdown("- " + esc(line))

    a, b, c = st.columns(3)
    if a.button("🔁 Same settings, new random data", key=f"pl_rerun_{item['k']}", width="stretch"):
        _launch(s, exp, kind="rerun", pred=None)
    if b.button("📊 Run it 200 times", key=f"pl_rep_{item['k']}", width="stretch",
                help="Shows what usually happens with these settings, not just this one run."):
        t0 = time.time()
        rep = _replicate(json.dumps(item["exp"], sort_keys=True), 200, item["seed"])
        item["rep"] = {k: v for k, v in rep.items()}
        log(M, f"exp{item['k']}", "replicate", score=rep["cost"], latency_s=time.time() - t0,
            response={k: v for k, v in rep.items() if k != "changes"} | dict(
                changes=[{k: v for k, v in c.items() if k != "delays"} for c in rep["changes"]]))
        st.rerun()
    c.caption("To try something different, change any setting above and press **Run experiment** again.")
    rep = item.get("rep")
    if rep:
        st.markdown(f"**Across {rep['reps']} runs with these settings**")
        r1, r2, r3, r4 = st.columns(4)
        if rep["changes"]:
            f = min(range(len(rep["changes"])), key=lambda i: exp.changes[i].at)
            rc = rep["changes"][f]
            r1.metric("First change caught", f"{rc['detected']:.0%} of runs")
            r2.metric("Typical delay (median)", "–" if rc["delay_median"] is None else f"{rc['delay_median']:.0f} samples")
        r3.metric("False alarms per 100 quiet samples", f"{rep['false_alarms_per_100']:.2f}")
        r4.metric("Average cost", _money(rep["cost"]), help=f"8 in 10 runs between {_money(rep['cost_p10'])} and "
                                                              f"{_money(rep['cost_p90'])}")
        if rep["changes"]:
            st.image(fig_png(LP.replication_figure(rep, exp)), width="stretch")

    with st.form(f"pl_reflect_{item['k']}"):
        txt = st.text_area("What did this experiment teach you? What will you try next? (optional)",
                           value=item.get("reflection", ""), max_chars=1500, height=80)
        no_names_hint()
        if st.form_submit_button("Save my note") and txt.strip():
            item["reflection"] = txt.strip()
            log(M, f"exp{item['k']}", "text", item_id="PL_REFLECT", response=txt.strip())
            st.success("Saved.")


def _launch(s, exp: PL.Experiment, *, kind: str, pred: dict | None) -> None:
    probs = exp.problems()
    if probs:
        for p in probs:
            st.error(p)
        return
    k = len(s["history"]) + 1
    seed = seed_for(M, 1000 + k)
    d = exp.to_dict()
    prev = s["history"][-1]["exp"] if s["history"] else None
    changed = PL.diff(prev, d)
    goal = st.session_state.get("pl_goal", "explore")
    t_setup = time.time() - s.get("t_last", s["t0"])
    log(M, f"exp{k}", "decision", response=d, latency_s=t_setup,
        detail=dict(kind=kind, changed=changed, n_changed=len(changed), goal=goal,
                    goal_text=st.session_state.get("pl_goal_text", "").strip()[:300], seed=seed))
    r = PL.run(exp, seed)
    summ = _summary(r)
    item = dict(k=k, exp=d, seed=seed, kind=kind, changed=changed, goal=goal, summary=summ, pred=pred)
    if pred:
        sc = _score_predictions(pred, exp, r)
        item["pred_score"] = sc
        log(M, f"exp{k}", "prediction", response={k2: v for k2, v in pred.items() if k2 != "confidence"},
            confidence=pred.get("confidence"), correct=sc.get("detect_correct"),
            score=sc.get("delay_abs_error"), detail=sc)
    log(M, f"exp{k}", "result", score=summ["costs"]["total"], response=summ)
    s["history"].append(item)
    s["t_last"] = time.time()
    st.rerun()


def _history(s) -> None:
    if not s["history"]:
        return
    rows = []
    for it in s["history"]:
        e, sm = it["exp"], it["summary"]
        first = min(sm["changes"], key=lambda c: c["at"]) if sm["changes"] else None
        rows.append({
            "#": it["k"], "chart": {"shewhart": PL.shewhart_name(e["process"]["n"]), "ewma": "EWMA",
                                    "cusum": "CUSUM"}[e["monitor"]["chart"]],
            "n": e["process"]["n"], "rules": e["monitor"]["rules"] if e["monitor"]["chart"] == "shewhart" else "–",
            "changes": ", ".join(f"{c['kind']}@{c['at']}" for c in e["changes"]) or "none",
            "changed since last": "new random data" if it["kind"] == "rerun" else (", ".join(
                x.split(".")[-1] for x in it["changed"]) or "–"),
            "first change caught after": ("–" if first is None else
                                          (f"{first['delay']}" if first["detected"] else "missed")),
            "false alarms": sm["false_alarms"], "out of spec %": round(100 * sm["oos_share"], 3),
            "cost $": round(sm["costs"]["total"]),
        })
    df = pd.DataFrame(rows)
    with st.expander(f"📒 Your experiments so far ({len(rows)})", expanded=len(rows) > 1):
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button("Download my experiments (CSV)", df.to_csv(index=False).encode(),
                           "my_process_lab_experiments.csv", "text/csv")


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def run() -> None:
    s = mstate(M)
    s.setdefault("changes", [])
    s.setdefault("history", [])
    s.setdefault("t0", time.time())
    start_mission(M)
    _defaults()

    c1, c2 = st.columns([5, 1])
    c1.markdown("### 🧪 Process Lab")
    c1.caption("Design your own experiments: set up a process, decide what goes wrong, choose how to watch it, "
               "predict, run. Every number and chart is generated from your settings.")
    if c2.button("← Learning Lab", key="pl_back"):
        go("home")
    if not s["history"]:
        insight("**How it works.** Real processes vary a little all the time (common causes) and sometimes change "
                "(special causes). A control chart is supposed to ignore the first and catch the second. Here you "
                "control both, so you can test any idea: *How big a shift can a sample of 3 catch? Does EWMA beat "
                "a Shewhart chart? What does a false alarm cost? What happens if the baseline is contaminated?*")

    _process_section()
    _changes_section(s)
    _monitor_section()

    if s["history"]:
        _show_result(s, s["history"][-1])
        _history(s)
    exp = _experiment(s)
    k = len(s["history"]) + 1
    with st.container(border=True):
        st.markdown(f"#### 4 · Experiment {k}: goal, prediction, run" if k == 1 else
                    f"#### Next: experiment {k}. Change any setting above, then predict and run")
        a, b = st.columns([2, 3])
        a.selectbox("What are you trying to find out?", list(GOALS), format_func=GOALS.get, key="pl_goal")
        if st.session_state.pl_goal == "own":
            b.text_input("Your question", key="pl_goal_text", max_chars=200,
                         placeholder="e.g. Is a sample of 2 every hour better than 8 every four hours?")
        with st.form(f"pl_run_{k}"):
            pred = _prediction_form(exp, k)
            go_run = st.form_submit_button("▶ Run experiment", type="primary")
        if go_run:
            if pred is not None:
                missing = []
                if exp.changes and pred.get("detect") is None:
                    missing.append("whether the chart will signal")
                if pred.get("false_alarms") is None:
                    missing.append("false alarms")
                if pred.get("oos_pct") is None:
                    missing.append("share out of spec")
                if missing:
                    st.error("Please predict " + ", ".join(missing) + " first.")
                    go_run = False
            if go_run:
                _launch(s, exp, kind="new", pred=pred)

    if s["history"]:
        st.divider()
        a, b = st.columns([3, 1])
        a.caption("Run as many experiments as you like. When you're done, finish the Process Lab to save your work.")
        if M not in lab()["done"]:
            if b.button("✅ Finish Process Lab", type="primary", width="stretch"):
                hist = s["history"]
                complete_mission(M, dict(
                    headline=f"{len(hist)} experiment{'s' if len(hist) != 1 else ''} run",
                    experiments=len(hist), reruns=sum(h["kind"] == "rerun" for h in hist),
                    replications=sum("rep" in h for h in hist),
                    one_factor_changes=sum(len(h["changed"]) == 1 for h in hist if h["kind"] == "new"),
                    notes=sum(bool(h.get("reflection")) for h in hist)))
                st.rerun()
        else:
            b.success("Finished ✓ (you can keep experimenting)")
