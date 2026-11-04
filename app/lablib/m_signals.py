"""Mission: Signal or Noise?"""
from __future__ import annotations

import numpy as np
import streamlit as st

from qualitylab.learn import plots as LP
from qualitylab.learn import signals as S

from .core import (
    complete_mission,
    confidence,
    esc,
    fig_png,
    go,
    header,
    insight,
    log,
    mstate,
    no_names_hint,
    seed_for,
    show,
    shown,
    start_mission,
)

M = "signals"
STEPS = ["The game", "Round 1: your instinct", "What the experts look for", "Round 2: with the rules", "Results"]


@st.cache_data(max_entries=4000, show_spinner=False)
def _chart_png(round_dict: dict, zones: bool, reveal: bool) -> bytes:
    """Charts are re-shown on every click; draw each one once."""
    return fig_png(LP.signal_chart(S.Round(**round_dict), zones=zones, reveal=reveal).figure)


def _phase_rounds(s, phase: str):
    key = f"rounds_{phase}"
    if key not in s:
        s[key] = [r.__dict__ for r in S.make_phase(phase, seed_for(M, 1 if phase == "A" else 2))]
    return [S.Round(**d) for d in s[key]]


def _play(s, phase: str, zones: bool) -> bool:
    """Returns True when the phase is finished."""
    rounds = _phase_rounds(s, phase)
    idx = s.setdefault(f"i_{phase}", 0)
    res = s.setdefault(f"res_{phase}", [])
    if idx >= len(rounds):
        return True
    r = rounds[idx]
    money = sum(x["payoff"] for x in s.get("res_A", []) + s.get("res_B", []))
    a, b = st.columns([3, 1])
    a.markdown(f"**Chart {idx + 1} of {len(rounds)}** · {esc(r.context['story'])}")
    b.metric("Your money so far", f"${money:,}")
    answered = len(res) > idx
    st.image(_chart_png(s[f"rounds_{phase}"][idx], zones, answered), width="stretch")
    if not answered:
        shown(f"sig_{r.round_id}")
        with st.form(f"sig_{r.round_id}"):
            st.markdown("Control limits come from the previous month, when the process ran normally. "
                        "**Has something changed that you should investigate?**")
            dec = st.radio("Decision", ["Investigate (costs $300)", "Leave it alone"], index=None, horizontal=True,
                           label_visibility="collapsed")
            conf = confidence(f"sig_conf_{r.round_id}")
            sub = st.form_submit_button("Decide", type="primary")
        if sub:
            if dec is None:
                st.error("Choose to investigate or leave it alone.")
                return False
            inv = dec.startswith("Investigate")
            pay = S.payoff(r.is_signal, inv)
            out = S.outcome_label(r.is_signal, inv)
            res.append(dict(round_id=r.round_id, investigate=inv, correct=inv == r.is_signal, payoff=pay,
                            outcome=out, category=r.category, confidence=conf))
            log(M, f"phase{phase}", "decision", item_id=r.round_id, response=dict(investigate=inv),
                correct=inv == r.is_signal, confidence=conf, score=pay, timer=f"sig_{r.round_id}",
                detail=dict(category=r.category, is_signal=r.is_signal, kind=r.kind, start=r.start,
                            context=r.context["name"], rules_fired=r.rules_fired, zones=zones))
            st.rerun()
        return False
    last = res[idx]
    emoji = {"hit": "✅ Good catch", "correct pass": "✅ Right call", "false alarm": "❌ False alarm",
             "miss": "❌ Missed it"}[last["outcome"]]
    money_txt = f"{'+' if last['payoff'] > 0 else '−' if last['payoff'] < 0 else ''}${abs(last['payoff']):,}"
    (st.success if last["correct"] else st.error)(esc(f"**{emoji}** ({money_txt}). {S.explain(r)}"))
    if st.button("Next chart →" if idx + 1 < len(rounds) else "Finish this round →", type="primary"):
        s[f"i_{phase}"] = idx + 1
        st.rerun()
    return False


def _summary(res) -> dict:
    sig = [x for x in res if x["category"].startswith("signal")]
    noi = [x for x in res if not x["category"].startswith("signal")]
    hits = sum(x["investigate"] for x in sig)
    fas = sum(x["investigate"] for x in noi)
    d = S.dprime(hits, len(sig), fas, len(noi))
    d.update(accuracy=float(np.mean([x["correct"] for x in res])), money=sum(x["payoff"] for x in res),
             hits=hits, false_alarms=fas, n_signal=len(sig), n_noise=len(noi),
             tempting_false_alarms=sum(x["investigate"] for x in noi if x["category"] == "noise_tempting"),
             subtle_hits=sum(x["investigate"] for x in sig if x["category"] == "signal_subtle"))
    return d


def run() -> None:
    s = mstate(M)
    start_mission(M)
    step = s["step"]
    header(M, step, STEPS)

    if step == 0:
        st.markdown(f"""
You are an operations analyst. Every chart shows **25 days** of a key measure from a different business, with
control limits from last month. For each one, decide: **investigate** or **leave it alone**?

| | Something really changed | Nothing changed |
|---|---|---|
| **Investigate** | You catch it: **+${S.COST_MISS - S.COST_INVESTIGATE:,}** | Wasted investigation: **−${S.COST_INVESTIGATE:,}** |
| **Leave it alone** | The problem keeps costing: **−${S.COST_MISS:,}** | **$0** |

Round 1 tests your instinct. Then you'll learn the rules professionals use, and play Round 2.
""".replace("$", r"\$"))
        if st.button("Start Round 1 →", type="primary"):
            s["step"] = 1
            st.rerun()
        return

    if step == 1:
        if _play(s, "A", zones=False):
            sm = _summary(s["res_A"])
            s["sum_A"] = sm
            log(M, "phaseA", "score", score=sm["dprime"], response=sm)
            s["step"] = 2
            st.rerun()
        return

    if step == 2:
        sm = s["sum_A"]
        st.markdown(f"**Round 1:** {sm['hits']} of {sm['n_signal']} real changes caught, "
                    f"{sm['false_alarms']} false alarm(s) out of {sm['n_noise']} normal charts, "
                    f"money {'+' if sm['money'] >= 0 else '−'}${abs(sm['money']):,}.".replace("$", r"\$"))
        st.markdown("### How professionals read a control chart")
        st.markdown("""
Points bounce around the center line all the time; that is **common-cause variation**, and reacting to it wastes
money. A **special cause** (a real change) shows up as one of these patterns. When nothing has changed, each has
less than a 1 % chance of appearing at any given point:
""")
        for t in S.RULE_TEXT.values():
            st.markdown(f"- **{t}**")
        st.markdown("The shaded bands mark 1σ and 2σ from the center line, which makes the last two rules easy to see.")
        ex = S.make_round("signal_subtle", np.random.default_rng(seed_for(M, 5)), phase="ex", round_id="ex",
                          context=S.CONTEXTS[1])
        show(LP.signal_chart(ex, zones=True, reveal=True).figure)
        st.caption(esc("Example: " + S.explain(ex)))
        insight("Two traps: a **single point close to a limit** (but inside it) is not a signal, and a **sustained "
                "shift can hide inside the limits**. Look for patterns, not just points beyond the lines.")
        if st.button("Start Round 2 →", type="primary"):
            s["step"] = 3
            st.rerun()
        return

    if step == 3:
        if _play(s, "B", zones=True):
            sm = _summary(s["res_B"])
            s["sum_B"] = sm
            log(M, "phaseB", "score", score=sm["dprime"], response=sm)
            s["step"] = 4
            st.rerun()
        return

    if step == 4:
        a, b = s["sum_A"], s["sum_B"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Correct calls", f"{a['accuracy']:.0%} → {b['accuracy']:.0%}")
        c2.metric("Real changes caught", f"{a['hits']}/{a['n_signal']} → {b['hits']}/{b['n_signal']}")
        c3.metric("False alarms", f"{a['false_alarms']} → {b['false_alarms']}")
        show(LP.dprime_chart({"Round 1": a["dprime"], "Round 2": b["dprime"]}).figure)
        st.caption("d′ (“d-prime”) measures how well you tell signals from noise, regardless of how cautious you "
                   "are: 0 = guessing; above 2 = very good.")
        if b["tempting_false_alarms"]:
            insight("You still investigated a chart where one point was merely *close* to a limit. With 25 points, "
                    "one landing beyond 2σ is expected about two times in three.")
        if b["subtle_hits"] < 3:
            insight("Some changes never put a point outside the limits. Runs on one side of the center line and "
                    "clusters beyond 1σ or 2σ catch them.")
        if "reflection" not in s:
            shown("sig_reflect")
            with st.form("sig_reflect"):
                txt = st.text_area("A colleague says: “If every point is inside the control limits, everything is "
                                   "fine.” How would you respond, using what you saw in this mission?", max_chars=1200)
                no_names_hint()
                sub = st.form_submit_button("Finish mission", type="primary")
            if sub:
                s["reflection"] = txt.strip()
                if txt.strip():
                    log(M, "reflect", "text", item_id="SIG_INSIDE", response=txt.strip(), timer="sig_reflect")
                complete_mission(M, dict(
                    headline=f"accuracy {a['accuracy']:.0%} → {b['accuracy']:.0%}; d′ {a['dprime']:.2f} → {b['dprime']:.2f}",
                    score=b["accuracy"], dprime_A=a["dprime"], dprime_B=b["dprime"],
                    money=a["money"] + b["money"]))
                st.rerun()
            return
        st.success("Mission complete! 🎉")
        if st.button("← Back to all missions", type="primary"):
            go("home")
