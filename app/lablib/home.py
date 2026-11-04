"""Consent, home screen, concept checks, survey and the student's learning record."""
from __future__ import annotations

import html
import json
from datetime import datetime

import numpy as np
import streamlit as st

from qualitylab import research, teaching
from qualitylab.learn import concepts as C

from .core import GUIDED, MISSIONS, ask_predictions, cfg, collecting, go, lab, log, seed_for, shown

# ---------------------------------------------------------------------------
# consent
# ---------------------------------------------------------------------------


def consent_view() -> None:
    c = cfg()
    st.title("🎓 Learning Lab")
    st.subheader("Before you start: an optional research study")
    st.markdown(f"""
**Study:** {c.study_title or "Learning quality management with interactive simulations"}
**Researchers:** {c.pi_name} ({c.pi_email}){(" · " + c.institution) if c.institution else ""}
**IRB protocol:** {c.irb_protocol}

We are studying how interactive simulations help students learn quality management. If you agree, the answers,
predictions and decisions you make in the Learning Lab will be stored **without your name** and analysed for
research.

- **Voluntary.** Taking part or not has **no effect on your grade**. You get exactly the same Learning Lab either way.
- **Anonymous.** We do not record your name, email, student ID or IP address. You will create a code from three
  answers only you know; we store a scrambled version of it, which lets us link your answers across sessions but
  not identify you.
- **What is stored:** your answers to the concept check and survey; the experiments you design in the Process Lab
  (your settings, predictions and results) and your decisions in the missions; how long steps took; and any short
  written notes.
- **Your choices:** you can skip any question and stop at any time. {c.data_access_note}
- **Risks and benefits:** there are no risks beyond those of a normal class activity. You may learn the course
  material more deeply; the results may improve how quality management is taught.
- **Questions:** contact {c.pi_name} at {c.pi_email}.{(" Questions about your rights as a participant: " + c.irb_contact + ".") if c.irb_contact else ""}
""")
    adult = st.checkbox("I am 18 years of age or older.", key="consent_adult")
    a, b = st.columns(2)
    if a.button("✅ I agree to take part", type="primary", width="stretch", disabled=not adult):
        st.session_state.consent_step = "code"
        st.rerun()
    if b.button("No thanks: use the Learning Lab without taking part", width="stretch"):
        lab()["consent"] = False
        go("home")
    if not adult:
        st.caption("If you are under 18, please choose “No thanks”. You can use everything in the Learning Lab.")


def name_view() -> None:
    """Participation record (teaching use): the student's name, before anything else."""
    st.title("🎓 Learning Lab")
    st.subheader("Your name, for participation")
    st.markdown("Your instructor records **who uses the Learning Lab and what they do in it** (for example, the "
                "experiments you run and the checks you complete) to see participation. The record is kept by your "
                "instructor and is not shared. Your answers in the Learning Lab are **not graded**: try things, make "
                "mistakes, change your mind.")
    with st.form("student_name"):
        name = st.text_input("Your first and last name, as on the class roster", max_chars=60)
        ok = st.form_submit_button("Continue", type="primary")
    if ok:
        try:
            lab()["student"] = teaching.clean_name(name)
        except ValueError as e:
            st.error(str(e))
            return
        log("participation", "start", "start")
        st.rerun()


def code_view() -> None:
    st.title("🎓 Learning Lab")
    st.subheader("Create your anonymous code")
    st.write("Answer three questions. Use the same answers every time you come back, so your sessions can be linked. "
             "Your answers are scrambled before anything is stored.")
    with st.form("sgic"):
        vals = [st.text_input(q, placeholder=ph, max_chars=n + 8) for q, ph, n, _ in research.SGIC_QUESTIONS]
        ok = st.form_submit_button("Create my code", type="primary")
    if ok:
        try:
            pid = research.participant_id(vals, cfg().salt)
        except ValueError as e:
            st.error(str(e))
            return
        L = lab()
        L["pid"], L["consent"] = pid, True
        L["condition"] = research.assign_condition(pid, cfg().conditions)
        log("consent", "consent", "consent", response=dict(agreed=True, adult=True))
        st.session_state.consent_step = None
        go("home")
    if st.button("← Back"):
        st.session_state.consent_step = None
        st.rerun()


# ---------------------------------------------------------------------------
# home
# ---------------------------------------------------------------------------

def home_view() -> None:
    L = lab()
    st.title("🎓 Learning Lab")
    st.markdown("#### Learn quality management by experimenting.")
    st.write("In the **Process Lab** you set up a process of your own, decide what goes wrong, choose how to watch "
             "it and run the experiment: every number and chart comes from your settings. "
             + ("Before each run you **predict** what will happen, then compare. " if ask_predictions() else "")
             + "Surprises are part of the design: they are where the learning happens.")
    if L.get("student"):
        st.caption(f"Signed in for participation as **{L['student']}**. Not you? Close this tab and open the app again.")
    if collecting():
        st.caption(f"Research participation: on · your code **{L['pid']}** (write it down if you want to withdraw later)")
    elif cfg().active and L["consent"] is False:
        st.caption("Research participation: off. Nothing you do here is stored.")

    done = L["done"]
    pl = L["m"].get("processlab", {})
    n_exp = len(pl.get("history", []))
    n_guided = sum(m in done for m in GUIDED)

    with st.container(border=True):
        a, b = st.columns([4, 1])
        a.markdown("**Step 1 · Warm-up check** (12 questions, about 6 minutes)  \n"
                   "See what you already know. You won't see the answers yet; you'll take the same check at the end."
                   + ("  \n*Coming back for a second session? Skip this and go straight to the Process Lab.*"
                      if collecting() and L["pre"] is None else ""))
        if L["pre"] is None:
            if b.button("Start", key="go_pre", type="primary", width="stretch"):
                go("pre")
        else:
            b.success("Done")

    with st.container(border=True):
        a, b = st.columns([4, 1])
        m = MISSIONS["processlab"]
        a.markdown(f"**Step 2 · {m['icon']} {m['title']}** (as long as you like; 30 minutes is a good start)  \n"
                   "Set up any process: what is measured, its target and specification, how much it varies. Decide "
                   "what goes wrong and when: a shift, a drift, more variation, an outlier. Choose the chart, the rules "
                   "and the sample size. Predict, run, compare, change one thing, run again.")
        if n_exp:
            a.caption(f"{n_exp} experiment{'s' if n_exp != 1 else ''} so far"
                      + (" · finished" if "processlab" in done else ""))
        if b.button("Continue" if n_exp else "Open", key="go_processlab", type="primary", width="stretch"):
            go("processlab")

    with st.expander(f"Optional: six short guided missions ({n_guided} of {len(GUIDED)} done)"):
        st.caption("Classic quality-management experiences in about 10 to 15 minutes each: Deming's red beads, "
                   "spotting signals, the funnel, capability, cost of quality and the economics of monitoring.")
        cols = st.columns(3)
        for i, key in enumerate(GUIDED):
            m = MISSIONS[key]
            with cols[i % 3].container(border=True, height=275):
                st.markdown(f"**{m['icon']} {m['title']}**")
                st.caption(f"{m['topic']} · ~{m['minutes']} min")
                st.write(m["hook"])
                label = "✓ Review" if key in done else ("Continue" if key in L["m"] else "Start")
                if st.button(label, key=f"go_{key}", width="stretch", type="secondary"):
                    go(key)

    with st.container(border=True):
        a, b = st.columns([4, 1])
        a.markdown("**Step 3 · Final check and feedback** (about 8 minutes)  \n"
                   "Retake the check to see how much you learned, with explanations, then tell us what worked.")
        if L["post"] is None:
            if b.button("Start", key="go_post", width="stretch", disabled=not (n_exp or done),
                        help="Run at least one experiment (or a mission) first."):
                go("post")
        elif L["survey"] is None:
            if b.button("Feedback", key="go_survey", width="stretch", type="primary"):
                go("survey")
        else:
            b.success("Done")

    st.divider()
    record_download()


# ---------------------------------------------------------------------------
# concept check
# ---------------------------------------------------------------------------

def n_opts_seed(item_id: str) -> int:
    return 1000 + int(item_id[1:])


def check_view(phase: str) -> None:
    L = lab()
    st.title("🎓 Learning Lab")
    st.subheader("Warm-up check" if phase == "pre" else "Final check")
    if L[phase] is not None:
        feedback_view(phase)
        return
    st.write("Choose the best answer and say how confident you are. "
             + ("There are no grades here; answer from what you know now." if phase == "pre"
                else "These are the same questions as the warm-up."))
    shown(f"check_{phase}")
    ids = C.order(seed_for("concepts", 1 if phase == "pre" else 2))
    with st.form(f"check_{phase}"):
        answers, conf = {}, {}
        for n, iid in enumerate(ids, 1):
            it = C.ITEM_BY_ID[iid]
            st.markdown(f"**{n}. {it.stem}**")
            # options in a per-student shuffled order (the same in both checks); values stay the original indices
            opts = [int(k) for k in np.random.default_rng(seed_for("options", n_opts_seed(iid))).permutation(
                len(it.options))]
            answers[iid] = st.radio("Answer", opts, index=None, key=f"{phase}_{iid}",
                                    format_func=lambda k, it=it: it.options[k], label_visibility="collapsed")
            conf[iid] = st.select_slider("Confidence", [1, 2, 3, 4, 5], value=3, key=f"{phase}_{iid}_c",
                                         format_func=lambda v: {1: "1 · guessing", 5: "5 · certain"}.get(v, str(v)))
            st.write("")
        sub = st.form_submit_button("Submit", type="primary")
    if st.button("← Back to the Lab"):
        go("home")
    if sub:
        missing = [n for n, iid in enumerate(ids, 1) if answers[iid] is None]
        if missing:
            st.error(f"Please answer question(s) {', '.join(map(str, missing))}.")
            return
        sc = C.score(answers)
        for iid in ids:
            log("concept", phase, "answer", item_id=iid, response=answers[iid], correct=sc["correct"][iid],
                confidence=conf[iid])
        log("concept", phase, "score", score=sc["pct"], timer=f"check_{phase}",
            response=dict(score=sc["score"], n=sc["n"]))
        L[phase] = dict(answers=answers, confidence=conf, **sc)
        st.rerun()


def feedback_view(phase: str) -> None:
    L = lab()
    r = L[phase]
    if phase == "pre":
        st.success("Thanks! Your warm-up is saved. You'll see the answers after the final check.")
        if st.button("Go to the missions →", type="primary"):
            go("home")
        return
    pre = L["pre"]
    a, b, c = st.columns(3)
    a.metric("Final check", f"{r['score']} / {r['n']}")
    if pre:
        b.metric("Warm-up", f"{pre['score']} / {pre['n']}")
        g = C.normalized_gain(pre["pct"], r["pct"])
        c.metric("Learning gain", "–" if g != g else f"{g:.0%}",
                 help="Share of what you didn't know at the start that you got right at the end (Hake's normalized gain).")
    for it in C.ITEMS:
        ok = r["correct"][it.id]
        was = pre["correct"][it.id] if pre else None
        tag = "✅" if ok else "❌"
        change = "" if was is None else (" · newly learned 🎉" if ok and not was else (" · slipped" if was and not ok else ""))
        with st.expander(f"{tag} {it.concept}{change}"):
            st.markdown(f"**{it.stem}**")
            st.markdown(f"Your answer: {it.options[r['answers'][it.id]]}  \nCorrect answer: **{it.options[it.answer]}**")
            st.info(it.why)
    if st.button("Continue to the short feedback survey →", type="primary"):
        go("survey")


# ---------------------------------------------------------------------------
# survey
# ---------------------------------------------------------------------------

def survey_view() -> None:
    L = lab()
    st.title("🎓 Learning Lab")
    st.subheader("Your feedback")
    if L["survey"] is not None:
        st.success("Thank you! Your feedback is saved.")
        record_download()
        if st.button("← Back to the Lab"):
            go("home")
        return
    shown("survey")
    st.write("About 3 minutes. Every question is optional.")
    with st.form("survey"):
        st.markdown("**About the Learning Lab as a tool**")
        sus = [st.radio(t, [1, 2, 3, 4, 5], index=None, horizontal=True, key=f"sus{i}",
                        format_func=lambda v: {1: "1 · strongly disagree", 5: "5 · strongly agree"}.get(v, str(v)))
               for i, t in enumerate(C.SUS_ITEMS)]
        st.markdown("**About your learning**")
        learn = {k: st.radio(t, list(range(1, 6)), index=None, horizontal=True, key=f"learn_{k}",
                             format_func=lambda v: C.LIKERT5[v - 1])
                 for k, t in C.LEARNING_ITEMS if ask_predictions() or k != "L2"}  # L2 asks about predicting
        best = st.text_area("Which mission or moment helped you learn the most, and why?", max_chars=1500)
        worse = st.text_area("What was confusing or could be better?", max_chars=1500)
        st.caption("Please don't include names or other identifying details.")
        sub = st.form_submit_button("Submit feedback", type="primary")
    if sub:
        if all(v is not None for v in sus):
            log("survey", "sus", "score", score=C.sus_score(sus), response=sus)
        for i, v in enumerate(sus):
            if v is not None:
                log("survey", "sus", "answer", item_id=f"SUS{i + 1}", response=v)
        for k, v in learn.items():
            if v is not None:
                log("survey", "learning", "answer", item_id=k, response=v)
        if best.strip():
            log("survey", "open", "text", item_id="most_helpful", response=best.strip())
        if worse.strip():
            log("survey", "open", "text", item_id="improve", response=worse.strip())
        L["survey"] = dict(sus=sus, learn=learn, best=best, worse=worse)
        log("survey", "end", "complete", timer="survey")
        st.rerun()


# ---------------------------------------------------------------------------
# learning record
# ---------------------------------------------------------------------------

def record_html() -> str:
    L = lab()
    rows = []
    for e in L["record"]:
        if e["event_type"] in ("start",):
            continue
        resp = e["response"]
        try:
            resp = json.loads(resp) if resp else ""
        except json.JSONDecodeError:
            pass
        if isinstance(resp, (dict, list)):
            resp = json.dumps(resp)[:300]
        rows.append(f"<tr><td>{html.escape(e['ts_utc'][11:19])}</td><td>{html.escape(e['mission'])}</td>"
                    f"<td>{html.escape(e['step'])}</td><td>{html.escape(e['event_type'])}</td>"
                    f"<td>{html.escape(e['item_id'])}</td><td>{html.escape(str(resp))}</td>"
                    f"<td>{'' if e['correct'] == '' else ('✔' if e['correct'] else '✘')}</td>"
                    f"<td>{'' if e['score'] == '' else round(float(e['score']), 3)}</td></tr>")
    done = "".join(f"<li><b>{html.escape(MISSIONS[k]['title'])}</b>: {html.escape(v.get('headline', 'completed'))}</li>"
                   for k, v in L["done"].items() if k in MISSIONS)
    pre, post = L["pre"], L["post"]
    checks = ""
    if pre:
        checks += f"<li>Warm-up check: {pre['score']}/{pre['n']}</li>"
    if post:
        checks += f"<li>Final check: {post['score']}/{post['n']}</li>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Learning Lab record</title>
<style>body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#0b0b0b}}
table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{border-bottom:1px solid #e3e2de;padding:4px 6px;text-align:left;vertical-align:top}}</style>
</head><body><h1>QualityLab · Learning Lab record</h1>
<p>Generated {datetime.now():%B %d, %Y %H:%M}. This file lives only on your computer.</p>
<h2>Summary</h2><ul>{checks}{done or '<li>No missions completed yet.</li>'}</ul>
<h2>Everything you did</h2><table><tr><th>Time</th><th>Mission</th><th>Step</th><th>Type</th><th>Item</th>
<th>Your response</th><th>Correct</th><th>Score</th></tr>{''.join(rows)}</table></body></html>"""


def record_download() -> None:
    st.download_button("⬇️ Download my learning record (HTML)", record_html().encode(),
                       file_name="learning_lab_record.html", mime="text/html",
                       help="A summary of your answers and results. Your instructor may ask you to submit it.")
