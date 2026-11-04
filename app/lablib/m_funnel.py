"""Mission: The Tampering Trap (Deming's funnel)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from qualitylab.learn import funnel as F
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

M = "funnel"
N_PLAY = 15
STEPS = ["Your machine", "Run it yourself", "You vs. leaving it alone", "Four strategies", "Check & reflect"]
HELP_OPTIONS = ["Closer to 12.00 oz on average", "About the same", "Further from 12.00 oz on average"]
RULE_PRED_OPTIONS = list(F.RULES.values())
CHECK = dict(
    stem="A barista's espresso shots take between 26 and 32 seconds, and a control chart shows the process is "
         "stable. After a 31-second shot, what should the barista do?",
    options=["Grind finer for the next shot to bring it back toward 29 seconds",
             "Nothing about that one shot; to reduce the spread, change the system (grinder, dosing, training)",
             "Time the next three shots and average them before adjusting",
             "Ask the manager to widen the acceptable range"],
    answer=1)


def run() -> None:
    s = mstate(M)
    start_mission(M)
    if "noise" not in s:
        rng = np.random.default_rng(seed_for(M))
        s["noise"] = rng.normal(0, F.SIGMA, N_PLAY + 1).tolist()
        s["adj"] = []
    step = s["step"]
    header(M, step, STEPS)
    noise = np.asarray(s["noise"])

    if step == 0:
        st.markdown(f"""
You run a filling machine for 12-oz bottles of cold brew. Even when nothing is wrong, fills vary a little
(about ± {2 * F.SIGMA:.2f} oz) because of tiny differences in pressure, foam and timing. The machine has a dial that
moves its **aim** up or down.

You'll fill {N_PLAY} bottles. After each one you may turn the dial, or leave it. Your goal: keep the bottles as
close to **12.00 oz** as possible.
""")
        if ask_predictions():
            shown("fn_pred1")
            with st.form("fn_pred1"):
                predict_box("If you correct the dial after every bottle to cancel its error, will your bottles end up…")
                p = st.radio("prediction", list(range(3)), index=None, format_func=lambda k: HELP_OPTIONS[k],
                             label_visibility="collapsed")
                c = confidence("fn_pred1_c")
                sub = st.form_submit_button("Start filling →", type="primary")
            if sub:
                if p is None:
                    st.error("Make a prediction.")
                    return
                log(M, "predict_adjust", "prediction", response=p, correct=p == 2, confidence=c, timer="fn_pred1")
                s["pred1"] = p
                s["step"] = 1
                st.rerun()
        elif st.button("Start filling →", type="primary"):
            s["step"] = 1
            st.rerun()
        return

    if step == 1:
        adj = s["adj"]
        k = len(adj)                      # bottles already filled = k + 1
        rep = F.replay_manual(adj, noise)
        fills, aims = rep["fills"][: k + 1], rep["aims"][: k + 1]
        last = fills[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Bottle {k + 1}", f"{last:.2f} oz", f"{last - F.TARGET:+.2f} vs. target", delta_color="off")
        c2.metric("Machine aim", f"{aims[-1]:.2f} oz")
        c3.metric("Bottles left", N_PLAY - (k + 1))
        show(LP.funnel_chart(fills, aims, lim=0.45, title="Your bottles so far").figure)
        if k + 1 >= N_PLAY:
            st.success("All bottles filled.")
            if st.button("See how you did →", type="primary"):
                ti = F.tampering_index(adj, rep["fills"])
                me = F.replay_manual(adj, noise)["sd"]
                alone = F.run_rule(1, noise[:N_PLAY])["sd"]
                s["result"] = dict(sd_player=me, sd_alone=alone, **ti)
                log(M, "play", "result", score=me / alone, timer="fn_play",
                    response=dict(adjustments=[round(a, 3) for a in adj]),
                    detail=dict(fills=[round(float(x), 3) for x in rep["fills"][:N_PLAY]], sd_player=me,
                                sd_alone=alone, **ti))
                s["step"] = 2
                st.rerun()
            return
        shown("fn_play")
        with st.form(f"fn_turn_{k}"):
            a = st.number_input("Turn the dial by (oz; negative = aim lower, 0 = leave it)", -0.50, 0.50, 0.0, 0.01,
                                format="%.2f", key=f"fn_adj_{k}")
            sub = st.form_submit_button("Fill the next bottle →", type="primary")
        if sub:
            adj.append(float(a))
            st.rerun()
        return

    if step == 2:
        r = s["result"]
        rep = F.replay_manual(s["adj"], noise)
        alone = F.run_rule(1, noise[:N_PLAY])
        fig, axs = plt.subplots(1, 2, figsize=(11, 3.2), sharey=True)
        LP.funnel_chart(rep["fills"][:N_PLAY], rep["aims"][:N_PLAY], ax=axs[0], lim=0.45, title="You")
        LP.funnel_chart(alone["fills"], ax=axs[1], lim=0.45, title="Same machine, dial never touched", color="#1baf7a")
        show(fig)
        c1, c2, c3 = st.columns(3)
        c1.metric("Your typical error", f"{r['sd_player']:.3f} oz")
        c2.metric("Left alone", f"{r['sd_alone']:.3f} oz")
        c3.metric("You turned the dial", f"{r['share_adjusted']:.0%} of the time")
        st.caption("Typical error = root-mean-square distance from 12.00 oz. Both machines had exactly the same "
                   "random disturbances; the only difference is your dial.")
        if r["share_adjusted"] < 0.2:
            insight("You mostly left the machine alone, and that is the right instinct for a stable process.")
        elif r["sd_player"] > r["sd_alone"]:
            insight(f"Adjusting made things worse: your bottles were {r['sd_player'] / r['sd_alone'] - 1:.0%} further "
                    "from target on average. Each correction responded to random noise that would not repeat, so "
                    "it simply added a second dose of randomness. This is **tampering**.")
        else:
            insight("You came out close this time, but that was luck: on average, correcting every bottle doubles the "
                    "variance. The next step shows why.")
        if s.get("pred1") is not None:
            st.caption(f"You predicted: “{HELP_OPTIONS[s['pred1']]}”.")
        if st.button("Compare four strategies →", type="primary"):
            s["step"] = 3
            st.rerun()
        return

    if step == 3:
        if ask_predictions() and "pred2" not in s:
            shown("fn_pred2")
            with st.form("fn_pred2"):
                predict_box("Each strategy runs 100 bottles with the same random disturbances. Which will keep the "
                            "bottles closest to target?")
                p = st.radio("Strategy", list(range(4)), index=None, format_func=lambda k: RULE_PRED_OPTIONS[k],
                             label_visibility="collapsed")
                c = confidence("fn_pred2_c")
                sub = st.form_submit_button("Run all four →", type="primary")
            if sub:
                if p is None:
                    st.error("Pick a strategy.")
                    return
                s["pred2"] = p
                log(M, "predict_rule", "prediction", response=p + 1, correct=p == 0, confidence=c, timer="fn_pred2")
                st.rerun()
            return
        e = np.random.default_rng(seed_for(M, 3)).normal(0, F.SIGMA, 100)
        fig, axs = plt.subplots(2, 2, figsize=(11, 6), sharex=True)
        sds = {}
        for ax, rule in zip(axs.ravel(), F.RULES):
            rr = F.run_rule(rule, e)
            sds[rule] = rr["sd"]
            LP.funnel_chart(rr["fills"], ax=ax, lim=1.2, title=f"Strategy {rule}: typical error {rr['sd']:.2f} oz",
                            color="#2a78d6" if rule == 1 else "#eb6834")
        fig.tight_layout()
        show(fig)
        for rule, label in F.RULES.items():
            st.markdown(f"**{rule}.** {label}")
        if s.get("pred2") is not None:
            (st.success if s["pred2"] == 0 else st.info)(f"You predicted strategy {s['pred2'] + 1}.")
        insight("This is Deming's **funnel experiment**. Leaving a stable process alone (1) gives the least "
                "variation. Compensating each error (2) doubles the variance. Mirroring around the target (3) and "
                "aiming at the last result (4) make the process drift further and further away. Strategies 2–4 are "
                "everywhere in business: chasing last month's sales, re-tuning a process after every complaint, "
                "training each new hire from the last one.")
        if st.button("Last step →", type="primary"):
            s["step"] = 4
            st.rerun()
        return

    if step == 4:
        if "check" not in s:
            shown("fn_check")
            with st.form("fn_check"):
                st.markdown(f"**{CHECK['stem']}**")
                a = st.radio("ans", list(range(4)), index=None, format_func=lambda k: CHECK["options"][k],
                             label_visibility="collapsed")
                c = confidence("fn_check_c")
                txt = st.text_area("Where have you seen tampering at work or in daily life? (optional)", max_chars=1200)
                no_names_hint()
                sub = st.form_submit_button("Finish mission", type="primary")
            if sub:
                if a is None:
                    st.error("Answer the question.")
                    return
                s["check"] = a
                log(M, "check", "answer", item_id="FN_BARISTA", response=a, correct=a == CHECK["answer"],
                    confidence=c, timer="fn_check")
                if txt.strip():
                    log(M, "reflect", "text", item_id="FN_EXAMPLE", response=txt.strip())
                r = s["result"]
                complete_mission(M, dict(
                    headline=f"your error {r['sd_player']:.3f} oz vs. {r['sd_alone']:.3f} oz left alone",
                    score=float(a == CHECK["answer"]), sd_ratio=r["sd_player"] / r["sd_alone"],
                    tamper_slope=r["slope"], share_adjusted=r["share_adjusted"]))
                st.rerun()
            return
        ok = s["check"] == CHECK["answer"]
        (st.success if ok else st.warning)(esc(
            ("Right. " if ok else f"The best answer: “{CHECK['options'][CHECK['answer']]}”. ")
            + "A single shot inside the normal range is common-cause variation; adjusting after it is tampering."))
        st.success("Mission complete! 🎉")
        if st.button("← Back to all missions", type="primary"):
            go("home")
