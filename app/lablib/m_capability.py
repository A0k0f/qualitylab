"""Mission: Keep the Customer (capability)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from qualitylab.learn import capability_game as CG
from qualitylab.learn import plots as LP

from .core import (
    ask_predictions,
    complete_mission,
    confidence,
    esc,
    go,
    header,
    insight,
    log,
    mstate,
    no_names_hint,
    predict_box,
    seed_for,
    show,
    shown,
    start_mission,
)

M = "capability"
STEPS = ["The customer's demand", "Voice of the process vs. voice of the customer", "Sort the processes",
         "Win the contract", "Check & reflect"]
PPM_OPTIONS = ["Less than 0.1 %", "About 0.5 %", "About 2 %", "About 10 %", "More than 25 %"]
PPM_ANSWER = 2
MAX_TRIES = 3
CHECK = dict(
    stem="After adding 100 % final inspection, the plant manager tells the customer “our Cpk is now much better.” "
         "Is that right?",
    options=["Yes: fewer bad parts are shipped, so Cpk rises",
             "No: inspection removes bad parts but the process still makes them, so Cpk is unchanged",
             "Yes, as long as the inspectors are well trained",
             "No: Cpk can only be measured at the customer's site"],
    answer=1)


def run() -> None:
    s = mstate(M)
    start_mission(M)
    step = s["step"]
    header(M, step, STEPS)
    cp0, cpk0 = CG.cp_cpk(CG.MEAN0, CG.SIGMA0)

    if step == 0:
        st.markdown(f"""
Your machine shop turns steel shafts for an automotive customer who accounts for 40 % of your sales. The drawing
says **25.00 ± 0.05 mm** (anything below {CG.LSL} or above {CG.USL} mm is rejected).

The customer's new supplier policy: **Cpk must be at least {CG.REQUIRED_CPK}**, or the contract goes to a competitor
next quarter. Your process is stable (in statistical control); it averages **{CG.MEAN0} mm** with a standard
deviation of **{CG.SIGMA0} mm**.
""")
        show(LP.capability_chart(CG.MEAN0, CG.SIGMA0, CG.LSL, CG.USL, CG.TARGET,
                                 title="Your process today (shaded = outside the specification)").figure)
        if ask_predictions():
            shown("cap_pred")
            with st.form("cap_pred"):
                predict_box("Before any numbers: what share of today's shafts fall outside the specification, and can "
                            "the process meet the customer's requirement as it is?")
                p = st.radio("Share out of spec", list(range(5)), index=None, horizontal=True,
                             format_func=lambda k: PPM_OPTIONS[k])
                cap = st.radio("Can it meet Cpk ≥ 1.33 without changes?", ["Yes", "No"], index=None, horizontal=True)
                c = confidence("cap_pred_c")
                sub = st.form_submit_button("Show me →", type="primary")
            if sub:
                if p is None or cap is None:
                    st.error("Answer both questions.")
                    return
                s["pred"] = (p, cap)
                log(M, "predict_ppm", "prediction", response=p, correct=p == PPM_ANSWER, confidence=c,
                    timer="cap_pred", detail=dict(truth_ppm=CG.ppm(CG.MEAN0, CG.SIGMA0)))
                log(M, "predict_capable", "prediction", response=cap, correct=cap == "No", confidence=c)
                s["step"] = 1
                st.rerun()
        elif st.button("Show me →", type="primary"):
            s["step"] = 1
            st.rerun()
        return

    if step == 1:
        ppm = CG.ppm(CG.MEAN0, CG.SIGMA0)
        c1, c2, c3 = st.columns(3)
        c1.metric("Out of specification", f"{ppm / 1e4:.1f} %", help=f"{ppm:,.0f} parts per million")
        c2.metric("Cp (spread only)", f"{cp0:.2f}")
        c3.metric("Cpk (spread and centering)", f"{cpk0:.2f}", f"{cpk0 - CG.REQUIRED_CPK:+.2f} vs. required",
                  delta_color="normal")
        if s.get("pred"):
            p, cap = s["pred"]
            st.caption(f"You predicted “{PPM_OPTIONS[p]}” and “{cap}”.")
        st.markdown(f"""
- **Cp = (USL − LSL) / 6σ = {cp0:.2f}.** The tolerance is wide enough for the spread, barely: the natural spread
  (±3σ = ±{3 * CG.SIGMA0:.3f} mm) fits inside ±0.05 mm.
- **Cpk = (distance from the mean to the nearer spec limit) / 3σ = {cpk0:.2f}.** The process runs
  {CG.MEAN0 - CG.TARGET:.2f} mm high, so its upper tail spills over the USL.
""")
        insight("The control chart says the process is **stable** (only common-cause variation). It does not say "
                "the process is **good enough**. Control limits are the *voice of the process*; specification limits "
                "are the *voice of the customer*. A process can be perfectly in control and still disappoint customers.")
        if st.button("Practice: sort four processes →", type="primary"):
            s["step"] = 2
            st.rerun()
        return

    if step == 2:
        rng = np.random.default_rng(seed_for(M, 2))
        keys = list(CG.QUADRANTS)
        perm = list(rng.permutation(keys))
        series = {k: CG.quadrant_series(k, rng) for k in perm}
        labels = {k: chr(ord("W") + i) for i, k in enumerate(perm)}  # W, X, Y, Z shown to students
        fig, axs = plt.subplots(1, 4, figsize=(12, 2.8), sharey=True)
        for ax, k in zip(axs, perm):
            LP.quadrant_chart(series[k], ax, labels[k])
        fig.tight_layout()
        show(fig)
        st.caption("Red solid lines: specification limits (the customer). Black dashed lines: control limits "
                   "(computed from each process's first 12 points). Green band: in specification.")
        if "sort" not in s:
            shown("cap_sort")
            with st.form("cap_sort"):
                ans = {}
                cols = st.columns(4)
                for col, k in zip(cols, perm):
                    col.markdown(f"**Process {labels[k]}**")
                    ic = col.radio("In control?", ["Yes", "No"], index=None, key=f"ic_{k}")
                    ca = col.radio("Capable (meets spec)?", ["Yes", "No"], index=None, key=f"ca_{k}")
                    ans[k] = (ic, ca)
                sub = st.form_submit_button("Check my answers", type="primary")
            if sub:
                if any(v is None for pair in ans.values() for v in pair):
                    st.error("Answer both questions for every process.")
                    return
                score = 0
                for k, (ic, ca) in ans.items():
                    q = CG.QUADRANTS[k]
                    ok_ic, ok_ca = (ic == "Yes") == q["in_control"], (ca == "Yes") == q["capable"]
                    score += ok_ic + ok_ca
                    log(M, "sort", "answer", item_id=f"Q{k}_control", response=ic, correct=ok_ic)
                    log(M, "sort", "answer", item_id=f"Q{k}_capable", response=ca, correct=ok_ca,
                        timer="cap_sort")
                s["sort"] = dict(score=score, ans=ans, labels=labels)
                st.rerun()
            return
        res = s["sort"]
        st.markdown(f"**You got {res['score']} of 8.**")
        for k in perm:
            q = CG.QUADRANTS[k]
            st.markdown(f"- **Process {res['labels'][k]}**: {'in control' if q['in_control'] else 'out of control'}, "
                        f"{'capable' if q['capable'] else 'not capable'}.")
        insight("Two separate questions: **Is it stable?** (control chart: patterns and points beyond the control "
                "limits) and **Is it good enough?** (spec limits). Fix stability first: capability numbers for an "
                "unstable process predict nothing.")
        if st.button("Now save the contract →", type="primary"):
            s["step"] = 3
            st.rerun()
        return

    if step == 3:
        tries = s.setdefault("tries", [])
        best = CG.cheapest_solution()
        solved = any(t["meets"] for t in tries)
        st.markdown(f"Choose any combination of actions. You need **Cpk ≥ {CG.REQUIRED_CPK}** at the **lowest "
                    f"cost**. You have {MAX_TRIES} tries.")
        if not solved and len(tries) < MAX_TRIES:
            shown(f"cap_try{len(tries)}")
            with st.form(f"cap_try{len(tries)}"):
                chosen = [k for k, a in CG.ACTIONS.items()
                          if st.checkbox(f"{a['label']} · ${a['cost']:,}".replace("$", r"\$"), key=f"cap_{len(tries)}_{k}")]
                sub = st.form_submit_button(f"Try it (attempt {len(tries) + 1} of {MAX_TRIES})", type="primary")
            if sub:
                o = CG.outcome(chosen)
                optimal = o["meets"] and o["cost"] <= best["cost"]
                tries.append(dict(chosen=chosen, **{k: o[k] for k in ("cp", "cpk", "cost", "meets", "ppm_made",
                                                                      "notes", "mean", "sigma")}, optimal=optimal))
                log(M, f"attempt{len(tries)}", "decision", response=sorted(chosen), correct=optimal,
                    score=o["cpk"], timer=f"cap_try{len(tries) - 1}",
                    detail=dict(cost=o["cost"], meets=o["meets"], best_cost=best["cost"]))
                st.rerun()
        for i, t in enumerate(tries, 1):
            with st.container(border=True):
                a, b = st.columns([2, 3])
                a.markdown(f"**Attempt {i}:** " + (", ".join(CG.ACTIONS[k]["label"].split(" (")[0] for k in t["chosen"])
                                                    or "no actions"))
                a.metric("Cpk", f"{t['cpk']:.2f}", "meets requirement" if t["meets"] else "below 1.33",
                         delta_color="normal" if t["meets"] else "inverse")
                a.metric("Cost", f"${t['cost']:,}")
                with b:
                    show(LP.capability_chart(t["mean"], t["sigma"], CG.LSL, CG.USL, CG.TARGET,
                                             compare=(CG.MEAN0, CG.SIGMA0)).figure)
                for n in t["notes"]:
                    st.info(esc(n))
        if solved or len(tries) >= MAX_TRIES:
            win = next((t for t in tries if t["meets"]), None)
            if win and win["optimal"]:
                st.success(esc(f"Contract saved at the lowest possible cost: ${best['cost']:,}. 🎉"))
            elif win:
                st.warning(esc(f"Contract saved, but you spent ${win['cost']:,}. The cheapest way costs ${best['cost']:,}."))
            else:
                st.error("The customer moves to a competitor next quarter.")
            st.markdown(esc("**Cheapest solution:** "
                            + " + ".join(CG.ACTIONS[k]["label"] for k in best["actions"])
                            + f" = ${best['cost']:,}, Cpk {best['cpk']:.2f}."))
            insight("Re-centering is cheap and fixes the *location* problem, but alone it only brings Cpk up to Cp "
                    f"({cp0:.2f}). Reducing variation raises Cp, and only centering lets Cpk reach it. Buying the "
                    "most expensive machine without centering still fails. Inspection and asking the customer to "
                    "relax the tolerance don't change the process at all.")
            if st.button("Last step →", type="primary"):
                s["step"] = 4
                st.rerun()
        return

    if step == 4:
        if "check" not in s:
            shown("cap_check")
            with st.form("cap_check"):
                st.markdown(f"**{CHECK['stem']}**")
                a = st.radio("ans", list(range(4)), index=None, format_func=lambda k: CHECK["options"][k],
                             label_visibility="collapsed")
                c = confidence("cap_check_c")
                txt = st.text_area("Explain to the plant manager, in two sentences, the difference between a process "
                                   "that is *in control* and one that is *capable*.", max_chars=1200)
                no_names_hint()
                sub = st.form_submit_button("Finish mission", type="primary")
            if sub:
                if a is None:
                    st.error("Answer the question.")
                    return
                s["check"] = a
                log(M, "check", "answer", item_id="CAP_INSPECT", response=a, correct=a == CHECK["answer"],
                    confidence=c, timer="cap_check")
                if txt.strip():
                    log(M, "reflect", "text", item_id="CAP_EXPLAIN", response=txt.strip())
                tries = s.get("tries", [])
                win = next((i for i, t in enumerate(tries, 1) if t["meets"]), None)
                complete_mission(M, dict(
                    headline=(f"met Cpk ≥ 1.33 on attempt {win}" if win else "did not meet the requirement")
                    + ("; found the cheapest solution" if any(t["optimal"] for t in tries) else ""),
                    score=float(any(t["optimal"] for t in tries)), attempts=len(tries), solved_on=win,
                    sort_score=s.get("sort", {}).get("score")))
                st.rerun()
            return
        ok = s["check"] == CHECK["answer"]
        (st.success if ok else st.warning)(esc(("Right. " if ok else f"The best answer: “{CHECK['options'][1]}”. ")
                                               + "Cpk describes what the process makes, not what survives inspection."))
        st.success("Mission complete! 🎉")
        if st.button("← Back to all missions", type="primary"):
            go("home")
