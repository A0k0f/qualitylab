"""Mission: Be the Quality Manager (economic design of monitoring)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from qualitylab import decision_plots as dp
from qualitylab.learn import manager_game as MG

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
    show,
    shown,
    start_mission,
)

M = "manager"
STEPS = ["The line", "Design your plan", "The verdict"]
MAX_TRIES = 3


@st.cache_resource(show_spinner="Simulating every plan for a year of production…")
def _simulated() -> tuple[pd.DataFrame, dict]:
    """Run once per server and shared by every student (read-only)."""
    df = MG.simulate_menu()
    today = df.attrs["today"]
    df.attrs = {}
    return df, today


def menu() -> pd.DataFrame:
    return _simulated()[0]


def today() -> dict:
    return _simulated()[1]


def _money(x: float) -> str:
    return f"${x / 1e3:,.0f}k" if abs(x) >= 1e4 else f"${x:,.0f}"


def _breakdown(rows: dict[str, dict]) -> pd.DataFrame:
    out = {}
    for label, r in rows.items():
        out[label] = {k.split(":", 1)[1]: v for k, v in r.items() if k.startswith("part:")}
    return pd.DataFrame(out).T


def run() -> None:
    s = mstate(M)
    start_mission(M)
    step = s["step"]
    header(M, step, STEPS)
    t = MG.scenario()
    P = t.process
    tod = today()

    if step == 0:
        st.markdown(f"""
You are the new quality manager of a **cold-brew filling line**: {P.units_per_hour:,.0f} bottles an hour,
{P.hours_per_day:.0f} hours a day. Three things go wrong from time to time:

- a nozzle partly clogs (bottles come out about 0.12 oz light) roughly every 5 days,
- the fill valve slowly drifts, roughly every 10 days,
- pressure surges make fills erratic, roughly every 15 days.

An underfilled bottle that reaches a retailer costs **\\$1.50** in chargebacks. Every check costs a technician's
time; every false alarm stops the line (**\\$120**); fixing a real problem costs **\\$300**. Overfilled bottles give product away
(**\\$0.06** per ounce above 12 oz, on every bottle).

**Today:** {esc(tod['plan'])}. That costs about **{esc(_money(tod['annual_cost']))} a year**, all in.
""")
        if ask_predictions() and "pred" not in s:
            shown("mg_pred")
            with st.form("mg_pred"):
                predict_box("With a smarter plan, what do you think is the lowest yearly cost achievable?")
                p = st.number_input("Lowest achievable cost per year ($)", 0, 1_000_000, value=None, step=5_000)
                c = confidence("mg_pred_c")
                sub = st.form_submit_button("Design my plan →", type="primary")
            if sub:
                if p is None:
                    st.error("Enter a number.")
                    return
                best = float(menu()["annual_cost"].min())
                s["pred"] = p
                log(M, "predict_best", "prediction", response=p, score=(p - best) / best, confidence=c,
                    timer="mg_pred", detail=dict(truth=best))
                s["step"] = 1
                st.rerun()
        elif not ask_predictions() and st.button("Design my plan →", type="primary"):
            s["step"] = 1
            st.rerun()
        return

    df = menu()
    best_key = df["annual_cost"].idxmin()

    if step == 1:
        tries = s.setdefault("tries", [])
        if len(tries) < MAX_TRIES:
            shown(f"mg_try{len(tries)}")
            with st.form(f"mg_try{len(tries)}"):
                st.markdown(f"**Design your monitoring plan** (attempt {len(tries) + 1} of {MAX_TRIES})")
                a, b = st.columns(2)
                every = a.select_slider("Check every… (hours)", MG.EVERY, value=4, key=f"mg_e{len(tries)}")
                n = a.radio("Bottles per check", MG.SIZES, horizontal=True, key=f"mg_n{len(tries)}")
                rule = b.radio("Decision rule", list(MG.RULES), format_func=MG.RULES.get, key=f"mg_r{len(tries)}")
                final = b.radio("Before shipping", list(MG.FINALS), format_func=MG.FINALS.get, key=f"mg_f{len(tries)}")
                sub = st.form_submit_button("Simulate a year →", type="primary")
            if sub:
                k = f"{rule}|{n}|{every:g}|{final}"
                r = df.loc[k]
                tries.append(dict(key=k))
                log(M, f"attempt{len(tries)}", "decision", response=dict(every=every, n=n, rule=rule, final=final),
                    correct=k == best_key, score=float(r["regret_pct"]), timer=f"mg_try{len(tries) - 1}",
                    detail=dict(cost=float(r["annual_cost"]), rank=int(r["rank"]), of=len(df)))
                st.rerun()
        for i, tr in enumerate(tries, 1):
            r = df.loc[tr["key"]]
            with st.container(border=True):
                st.markdown(esc(f"**Attempt {i}:** {r['plan']}"))
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Cost per year", _money(r["annual_cost"]), _money(r["annual_cost"] - tod["annual_cost"]) +
                          " vs. today", delta_color="inverse")
                c2.metric("Problems fixed after", f"{r['hours_to_fix']:.1f} h")
                c3.metric("Bad bottles reaching retailers", f"{r['escapes_ppm']:,.0f} ppm",
                          help="ppm = parts per million bottles")
                c4.metric("Rank among 32 plans", f"#{int(r['rank'])}")
        if tries:
            last = df.loc[tries[-1]["key"]]
            show(dp.plot_cost_breakdown(_breakdown({"Today": tod, f"Attempt {len(tries)}": last.to_dict()})).figure)
        if len(tries) >= MAX_TRIES or (tries and tries[-1]["key"] == best_key):
            if st.button("See the verdict →", type="primary"):
                s["step"] = 2
                st.rerun()
        return

    if step == 2:
        tries = s.get("tries", [])
        best = df.loc[best_key]
        ranks = [int(df.loc[t["key"], "rank"]) for t in tries]
        st.markdown(esc(f"**Best plan on the menu:** {best['plan']}: {_money(best['annual_cost'])} a year, "
                        f"{_money(tod['annual_cost'] - best['annual_cost'])} less than today."))
        st.markdown("Your attempts ranked: " + " → ".join(f"#{r}" for r in ranks) + f" (out of {len(df)}).")
        if s.get("pred") is not None:
            st.caption(esc(f"You predicted the lowest achievable cost would be ${s['pred']:,.0f}."))
        top = df.sort_values("annual_cost").head(8)[["plan", "annual_cost", "hours_to_fix", "escapes_ppm",
                                                      "false_alarms_per_week"]]
        top.columns = ["Plan", "Cost / year", "Hours to fix", "Escapes per million", "False alarms / week"]
        st.dataframe(top.style.format({"Cost / year": "${:,.0f}", "Hours to fix": "{:.1f}",
                                       "Escapes per million": "{:,.0f}", "False alarms / week": "{:.2f}"}),
                     width="stretch", hide_index=True)
        insight("Three lessons: (1) a **control chart beats “stop only if a bottle is out of spec”**, because a clogged "
                "nozzle moves the average long before many bottles fall outside the spec; (2) **more checking is not "
                "always better**: very frequent checks cost more than they save; (3) **100 % inspection is "
                "expensive** sorting, not prevention. Explore more options in the full Decision Studio.")
        if "reflection" not in s:
            shown("mg_reflect")
            with st.form("mg_reflect"):
                txt = st.text_area("Your plant manager asks: “Why not just weigh every bottle?” Answer in two or three "
                                   "sentences.", max_chars=1200)
                no_names_hint()
                sub = st.form_submit_button("Finish mission", type="primary")
            if sub:
                s["reflection"] = txt.strip()
                if txt.strip():
                    log(M, "reflect", "text", item_id="MG_WHYNOT", response=txt.strip(), timer="mg_reflect")
                regrets = [float(df.loc[t["key"], "regret_pct"]) for t in tries]
                complete_mission(M, dict(
                    headline=f"best attempt ranked #{min(ranks)} of {len(df)}" if ranks else "no attempts",
                    score=1 - min(regrets) if regrets else 0.0, first_regret=regrets[0] if regrets else None,
                    best_regret=min(regrets) if regrets else None, attempts=len(tries)))
                st.rerun()
            return
        st.success("Mission complete! 🎉")
        if st.button("← Back to all missions", type="primary"):
            go("home")
