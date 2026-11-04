"""Mission: Where Does the Money Go? (cost of quality, Pareto, project selection)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from qualitylab.learn import pareto_game as PG
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

M = "pareto"
STEPS = ["Sort the costs", "Count vs. cost", "Spend the budget", "Reflect"]
MAX_TRIES = 3


def _money(x: float) -> str:
    return f"${x:,.0f}"


def run() -> None:
    s = mstate(M)
    start_mission(M)
    step = s["step"]
    header(M, step, STEPS)

    if step == 0:
        st.markdown("Every dollar a company spends because of quality falls into one of four buckets. **Sort these "
                    "eight costs.**")
        for cat in PG.COQ_CATEGORIES:
            st.caption(f"**{cat}:** {PG.COQ_WHY[cat]}")
        items = list(PG.COQ_ITEMS)
        order = np.random.default_rng(seed_for(M)).permutation(len(items))
        if "coq" not in s:
            shown("pg_coq")
            with st.form("pg_coq"):
                ans = {}
                for i in order:
                    text, _ = items[i]
                    ans[i] = st.selectbox(text, PG.COQ_CATEGORIES, index=None, key=f"coq_{i}",
                                          placeholder="Choose a category")
                sub = st.form_submit_button("Check", type="primary")
            if sub:
                if any(v is None for v in ans.values()):
                    st.error("Sort every cost.")
                    return
                score = 0
                for i, v in ans.items():
                    ok = v == items[i][1]
                    score += ok
                    log(M, "coq", "answer", item_id=f"COQ{i + 1}", response=v, correct=ok)
                log(M, "coq", "score", score=score / len(items), timer="pg_coq")
                s["coq"] = dict(ans=ans, score=score)
                st.rerun()
            return
        res = s["coq"]
        st.markdown(f"**{res['score']} of {len(items)} correct.**")
        for i in order:
            text, cat = items[i]
            mark = "✅" if res["ans"][i] == cat else f"❌ (you said {res['ans'][i]})"
            st.markdown(f"- {text} → **{cat}** {mark}")
        insight("Spending on **prevention** usually cuts failure costs by much more than it costs, which is why "
                "quality pioneers such as Crosby argued that “quality is free”. External failures are the most "
                "expensive, and partly invisible: lost customers never show up as a line in the accounts.")
        if st.button("Next: the complaints data →", type="primary"):
            s["step"] = 1
            st.rerun()
        return

    if step == 1:
        t = PG.COMPLAINTS
        st.markdown("You are the quality manager at an online furniture retailer. Here is last year's complaint data, "
                    "with what an average complaint of each kind costs (refunds, reshipping, staff time, credits).")
        view = t.copy()
        view.columns = ["Complaints per year", "Cost per complaint", "Annual cost"]
        st.dataframe(view.style.format({"Cost per complaint": "${:,.0f}", "Annual cost": "${:,.0f}"}),
                     width="stretch")
        if ask_predictions() and "pred" not in s:
            shown("pg_pred")
            with st.form("pg_pred"):
                predict_box("Which category is costing the company the most money?")
                p = st.radio("Category", list(t.index), index=None, label_visibility="collapsed")
                c = confidence("pg_pred_c")
                sub = st.form_submit_button("Show the Pareto charts →", type="primary")
            if sub:
                if p is None:
                    st.error("Pick a category.")
                    return
                s["pred"] = p
                truth = t["annual_cost"].idxmax()
                log(M, "predict_top", "prediction", response=p, correct=p == truth, confidence=c, timer="pg_pred",
                    detail=dict(truth=truth))
                st.rerun()
            return
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.2))
        LP.pareto_pair(t, a1, a2)
        fig.tight_layout()
        show(fig)
        if s.get("pred"):
            truth = t["annual_cost"].idxmax()
            (st.success if s["pred"] == truth else st.info)(f"You picked “{s['pred']}”. The most expensive is "
                                                             f"“{truth}”.")
        insight("Late deliveries generate the most complaints, but wrong items cost the most because each one means a "
                "return, a reshipment and a refund. **Rank by what matters to the business, not just by what is "
                "most frequent.** A Pareto chart is only as good as the measure you put on it.")
        if st.button("Next: spend the budget →", type="primary"):
            s["step"] = 2
            st.rerun()
        return

    if step == 2:
        pt = PG.project_table()
        best = PG.optimal()
        tries = s.setdefault("tries", [])
        st.markdown(f"You have **{_money(PG.BUDGET)}** for improvement projects this year. Each project cuts one "
                    "complaint category by the share shown. **Choose the portfolio that saves the most money per "
                    f"year without going over budget.** You have {MAX_TRIES} tries.")
        view = pt[["project", "category", "cost", "cut", "annual_saving"]].copy()
        view.columns = ["Project", "Fixes", "Cost", "Cuts complaints by", "Annual saving"]
        st.dataframe(view.style.format({"Cost": "${:,.0f}", "Cuts complaints by": "{:.0%}",
                                        "Annual saving": "${:,.0f}"}), width="stretch", hide_index=True)
        done = any(t["optimal"] for t in tries) or len(tries) >= MAX_TRIES
        if not done:
            shown(f"pg_try{len(tries)}")
            with st.form(f"pg_try{len(tries)}"):
                chosen = [k for k, row in pt.iterrows()
                          if st.checkbox(f"{row['project']} ({_money(row['cost'])})".replace("$", r"\$"),
                                         key=f"pg_{len(tries)}_{k}")]
                sub = st.form_submit_button(f"Fund these (attempt {len(tries) + 1} of {MAX_TRIES})", type="primary")
            if sub:
                e = PG.evaluate(chosen)
                if not e["within_budget"]:
                    st.error(esc(f"That costs {_money(e['cost'])}, over the {_money(PG.BUDGET)} budget. Try again "
                                 "(this doesn't count as an attempt)."))
                    return
                opt = abs(e["annual_saving"] - best["annual_saving"]) < 1e-6
                tries.append(dict(e, optimal=opt))
                log(M, f"attempt{len(tries)}", "decision", response=e["chosen"], correct=opt,
                    score=e["annual_saving"] / best["annual_saving"], timer=f"pg_try{len(tries) - 1}",
                    detail=dict(cost=e["cost"], saving=e["annual_saving"], best=best["annual_saving"]))
                st.rerun()
        for i, t in enumerate(tries, 1):
            st.markdown(esc(f"**Attempt {i}:** {', '.join(pt.loc[k, 'project'] for k in t['chosen'])} → cost "
                            f"{_money(t['cost'])}, saves **{_money(t['annual_saving'])} a year** "
                            f"({t['annual_saving'] / best['annual_saving']:.0%} of the best possible)."))
        if done:
            if any(t["optimal"] for t in tries):
                st.success("You found the best portfolio! 🎉")
            st.markdown(esc(f"**Best portfolio:** {', '.join(pt.loc[k, 'project'] for k in best['chosen'])}: cost "
                            f"{_money(best['cost'])}, saves {_money(best['annual_saving'])} a year."))
            rows = []
            for nm, by in (("Fund the most-complained-about first", "count"),
                           ("Fund the most expensive category first", "cost"),
                           ("Fund the best saving per dollar first", "ratio")):
                g = PG.greedy(by)
                rows.append(f"- {nm}: {_money(g['annual_saving'])} a year")
            st.markdown(esc("**How common rules of thumb do:**\n" + "\n".join(rows)))
            insight("Even “best saving per dollar first” misses the optimum, because it leaves money unspent. Choosing "
                    "a portfolio under a budget is a **knapsack problem**: the best answer comes from comparing whole "
                    "combinations, which is exactly what operations research tools do.")
            if st.button("Last step →", type="primary"):
                s["step"] = 3
                st.rerun()
        return

    if step == 3:
        if "reflection" not in s:
            shown("pg_reflect")
            with st.form("pg_reflect"):
                txt = st.text_area("Your CFO asks why you didn't start with late deliveries, the biggest source of "
                                   "complaints. What do you say?", max_chars=1200)
                no_names_hint()
                sub = st.form_submit_button("Finish mission", type="primary")
            if sub:
                s["reflection"] = txt.strip()
                if txt.strip():
                    log(M, "reflect", "text", item_id="PG_CFO", response=txt.strip(), timer="pg_reflect")
                tries = s.get("tries", [])
                best = PG.optimal()
                top = max((t["annual_saving"] for t in tries), default=0.0)
                complete_mission(M, dict(
                    headline=f"cost-of-quality sort {s['coq']['score']}/8; best portfolio "
                             f"{top / best['annual_saving']:.0%} of optimal",
                    score=top / best["annual_saving"], coq_score=s["coq"]["score"], attempts=len(tries),
                    found_optimal=any(t["optimal"] for t in tries)))
                st.rerun()
            return
        st.success("Mission complete! 🎉")
        if st.button("← Back to all missions", type="primary"):
            go("home")
