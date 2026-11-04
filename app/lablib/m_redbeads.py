"""Mission: The Red Bead Factory."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from qualitylab.learn import plots as LP
from qualitylab.learn import redbeads as RB

from .core import (
    ask_predictions,
    complete_mission,
    confidence,
    esc,
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

M = "redbeads"
STEPS = ["Day 1", "Day 2", "Day 3", "What explains it?", "The reveal", "Change the system", "Reflect"]
WHY_OPTIONS = [
    "Some workers are more skilled or careful than others",
    "Random variation produced by the system (beads, paddle, method)",
    "The manager's praise and warnings changed how people worked",
    "A mix of skill and effort, with a little luck",
]
WHY_ANSWER = 1


def _day_table(days) -> pd.DataFrame:
    df = pd.DataFrame({f"Day {d.day}": d.counts for d in days}).T
    df["Team total"] = df.sum(axis=1)
    return df


def _show_days(s) -> None:
    days = [RB.DayResult(d, c) for d, c in s["days"]]
    df = _day_table(days)
    st.dataframe(df.style.highlight_max(axis=1, subset=RB.WORKERS, color="#f4c7c3")
                 .highlight_min(axis=1, subset=RB.WORKERS, color="#cde8cd"), width="stretch")
    st.caption("Red = most red beads that day (worst); green = fewest (best). Each lot is 50 beads; the customer "
               "accepts only white beads. Management's goal: no more than 3 red beads per lot.")


def _decision_form(s, day: int) -> None:
    with st.form(f"rb_decide_{day}"):
        st.markdown(f"**Your decisions after Day {day}.** What do you do with each worker?")
        cols = st.columns(3)
        acts = {w: cols[i % 3].selectbox(w, RB.ACTIONS, key=f"rb_act_{day}_{w}") for i, w in enumerate(RB.WORKERS)}
        pred = {}
        if day == 1 and ask_predictions():
            predict_box("Before Day 2 runs, make two predictions.")
            pred["best_worker"] = st.selectbox("Who will have the fewest red beads tomorrow?", RB.WORKERS,
                                               index=None, key="rb_pred_best")
            pred["team_total"] = st.number_input("How many red beads will the whole team make tomorrow?", 0, 300,
                                                 value=None, key="rb_pred_total")
            pred["conf"] = confidence("rb_pred_conf")
        sub = st.form_submit_button(f"Run Day {day + 1} →", type="primary")
    if sub:
        if pred and (pred["best_worker"] is None or pred["team_total"] is None):
            st.error("Please make both predictions.")
            return
        s["actions"][day] = acts
        log(M, f"day{day}", "decision", response=acts, timer=f"rb_day{day}",
            detail=dict(counts=dict(s["days"][day - 1][1])))
        if pred:
            nxt = dict(s["days"][day][1])
            truth_best = min(nxt, key=nxt.get)
            s["prediction"] = dict(pred, truth_best=truth_best, truth_total=sum(nxt.values()))
            log(M, "predict_day2", "prediction", response=dict(best_worker=pred["best_worker"],
                                                                team_total=pred["team_total"]),
                confidence=pred["conf"], correct=pred["best_worker"] == truth_best,
                score=abs(pred["team_total"] - sum(nxt.values())),
                detail=dict(truth_best=truth_best, truth_total=sum(nxt.values())))
        s["step"] = day
        st.rerun()


def run() -> None:
    s = mstate(M)
    start_mission(M)
    if "days" not in s:
        rng = np.random.default_rng(seed_for(M))
        s["days"] = [(d, RB.scoop(rng)) for d in (1, 2, 3)]
        s["actions"] = {}
        s["seed"] = seed_for(M)
    step = s["step"]
    header(M, step, STEPS)

    if step == 0:
        st.markdown(
            "You are the new production manager at **White Bead Inc.** Six willing workers each produce one lot a "
            "day: they dip a paddle with 50 holes into a large bin of beads. Customers want **white** beads only. "
            "The beads come from a supplier; the method is fixed by management (that's you). Here is Day 1.")
        shown("rb_day1")
        _show_days({"days": s["days"][:1]})
        _decision_form(s, 1)
        return

    if step in (1, 2):
        shown(f"rb_day{step + 1}")
        _show_days({"days": s["days"][: step + 1]})
        if step == 1 and s.get("prediction"):
            p = s["prediction"]
            msg = (f"You predicted **{p['best_worker']}** would be best; it was **{p['truth_best']}**. "
                   f"You expected {p['team_total']} red beads for the team; they made {p['truth_total']}.")
            st.info(esc(msg))
        if step == 1:
            _decision_form(s, 2)
        else:
            st.markdown("Three days of results are in. Keep an eye on the workers you praised and warned.")
            if st.button("Continue →", type="primary"):
                s["step"] = 3
                st.rerun()
        return

    if step == 3:
        _show_days(s)
        shown("rb_why")
        with st.form("rb_why"):
            why = st.radio("**What best explains why some workers had more red beads than others?**",
                           list(range(len(WHY_OPTIONS))), index=None, format_func=lambda k: WHY_OPTIONS[k])
            conf = confidence("rb_why_conf")
            sub = st.form_submit_button("See what really happened →", type="primary")
        if sub:
            if why is None:
                st.error("Choose an answer.")
                return
            s["why"] = why
            log(M, "why", "answer", item_id="RB_WHY", response=why, correct=why == WHY_ANSWER, confidence=conf,
                timer="rb_why")
            s["step"] = 4
            st.rerun()
        return

    if step == 4:
        days = [RB.DayResult(d, c) for d, c in s["days"]]
        counts = [c for d in days for c in d.counts.values()]
        lim = RB.control_limits(counts)
        show(LP.bead_table_chart(days, lim, title="Every lot, Days 1–3, on an np control chart").figure)
        out = [c for c in counts if c > lim["ucl"] or c < lim["lcl"]]
        if s.get("why") == WHY_ANSWER:
            st.success("You saw it: the differences come from the system, not the people.")
        else:
            st.warning("Most people pick skill or effort. The chart tells a different story.")
        insight(
            (f"Every lot falls between the control limits ({lim['lcl']:.1f} to {lim['ucl']:.1f} red beads)" if not out
             else f"All but {len(out)} lot(s) fall between the control limits ({lim['lcl']:.1f} to {lim['ucl']:.1f} "
                  "red beads), and with 18 lots an occasional point outside is possible by chance")
            + ". The workers had no control over the beads: the bin is 20 % red, so each paddle averages about 10 "
              "red beads and varies by about ±3 from scoop to scoop. **Ranking, praising and warning people for "
              "results the system produces is futile.** This is Deming's core lesson: around 94 % of problems "
              "belong to the system, which only management can change.")
        eff = RB.intervention_effects(days, s["actions"])
        rtm = RB.regression_to_mean()
        if eff:
            parts = [f"after **{a.lower()}**, {v['mean_change']:+.1f} beads ({v['n']} case{'s' if v['n'] != 1 else ''})"
                     .replace("-", "−") for a, v in eff.items()]
            st.markdown("**In your factory**, a worker's red beads changed the next day by, on average: "
                        + "; ".join(parts) + ".")
        st.markdown(esc(
            f"**Across 100,000 simulated factories with no manager at all**, the worst worker of a day averaged "
            f"{rtm['worst_today']:.1f} red beads and then {rtm['worst_next']:.1f} the next day: an "
            f"“improvement” of {rtm['worst_today'] - rtm['worst_next']:.1f} beads. The best worker went from "
            f"{rtm['best_today']:.1f} to {rtm['best_next']:.1f}. Warnings seem to work and praise seems to backfire, "
            f"but both are just **regression to the mean**."))
        bi = RB.blame_index(s["actions"])
        s["blame_index"] = bi
        log(M, "reveal", "result", score=bi, response=dict(effects=eff), detail=dict(limits=lim, out_of_limits=len(out)))
        if st.button("Now fix the system →", type="primary"):
            s["step"] = 5
            st.rerun()
        return

    if step == 5:
        st.markdown("You have budget for **one** change before the next four days. Which will reduce the red beads "
                    "your customers receive the most?")
        keys = list(RB.SYSTEM_CHANGES)
        if "change" not in s:
            shown("rb_change")
            with st.form("rb_change"):
                ch = st.radio("Options", keys, index=None, label_visibility="collapsed",
                              format_func=lambda k: f"{RB.SYSTEM_CHANGES[k]['label']} (${RB.SYSTEM_CHANGES[k]['cost']:,})")
                pred = None
                if ask_predictions():
                    predict_box("With your change, how many red beads will the whole team make per day?")
                    pred = st.number_input("Red beads per day (team)", 0, 300, value=None, key="rb_pred_change")
                sub = st.form_submit_button("Run four more days →", type="primary")
            if sub:
                if ch is None or (ask_predictions() and pred is None):
                    st.error("Choose an option" + (" and make a prediction." if ask_predictions() else "."))
                    return
                rng = np.random.default_rng(seed_for(M, 9))
                after = RB.system_round(rng, ch)
                s["change"], s["after"] = ch, [(d.day + 3, d.counts) for d in after]
                shipped = [RB.shipped_red(d.counts, RB.SYSTEM_CHANGES[ch]["inspect"], rng) for d in after]
                s["shipped"] = shipped
                actual = float(np.mean([sum(d.counts.values()) for d in after]))
                log(M, "system_change", "decision", response=ch, correct=ch == "supplier", timer="rb_change",
                    detail=dict(red_per_day=actual, shipped_per_day=float(np.mean(shipped))))
                if pred is not None:
                    log(M, "predict_change", "prediction", response=pred, score=abs(pred - actual),
                        detail=dict(truth=actual))
                st.rerun()
            return
        ch = RB.SYSTEM_CHANGES[s["change"]]
        days = [RB.DayResult(d, c) for d, c in s["days"]] + [RB.DayResult(d, c) for d, c in s["after"]]
        before = [c for d in days[:3] for c in d.counts.values()]
        show(LP.bead_table_chart(days, RB.control_limits(before), split_at=18,
                                 title="Before and after your change (limits from Days 1–3)").figure)
        b = np.mean([sum(c.values()) for _, c in s["days"]])
        a = np.mean([sum(c.values()) for _, c in s["after"]])
        sh = np.mean(s["shipped"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Red beads made per day", f"{a:.0f}", f"{a - b:+.0f} vs. before", delta_color="inverse")
        c2.metric("Red beads shipped per day", f"{sh:.0f}", f"{sh - b:+.0f}", delta_color="inverse")
        c3.metric("Cost of the change", f"${ch['cost']:,}")
        if s["change"] == "supplier":
            st.caption("Points below the lower control limit are a signal too: here, a real improvement in the system.")
        (st.success if s["change"] == "supplier" else st.info)(esc(ch["why"]))
        if s["change"] != "supplier":
            st.markdown(esc("**The option that changes the system:** " + RB.SYSTEM_CHANGES["supplier"]["label"] + ". "
                            + RB.SYSTEM_CHANGES["supplier"]["why"]))
        if st.button("Last step: reflect →", type="primary"):
            s["step"] = 6
            st.rerun()
        return

    if step == 6:
        if "reflection" not in s:
            shown("rb_reflect")
            with st.form("rb_reflect"):
                txt = st.text_area("Your CEO wants to start a monthly “Employee of the Month” award based on defect "
                                   "counts. In two or three sentences, what would you advise, and why?", max_chars=1200)
                no_names_hint()
                sub = st.form_submit_button("Finish mission", type="primary")
            if sub:
                s["reflection"] = txt.strip()
                if txt.strip():
                    log(M, "reflect", "text", item_id="RB_CEO", response=txt.strip(), timer="rb_reflect")
                complete_mission(M, dict(
                    headline=("identified the system as the cause" if s.get("why") == WHY_ANSWER else
                              "learned the system, not the workers, drives results")
                    + f"; chose “{RB.SYSTEM_CHANGES[s['change']]['label']}”",
                    score=float(s.get("why") == WHY_ANSWER) * 0.5 + float(s["change"] == "supplier") * 0.5,
                    blame_index=s.get("blame_index"), why_correct=s.get("why") == WHY_ANSWER,
                    system_change=s["change"]))
                st.rerun()
            return
        st.success("Mission complete! 🎉")
        insight("A strong answer: rewards based on these numbers would be a lottery that punishes good people and "
                "breeds fear. Reward contributions to improving the system instead, and give management the job of "
                "fixing materials and methods.")
        if st.button("← Back to all missions", type="primary"):
            from .core import go

            go("home")
