"""Instructor & researcher dashboard for the Learning Lab (password protected)."""
from __future__ import annotations

import hmac
import io
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from qualitylab import research  # noqa: E402
from qualitylab import research_analysis as RA  # noqa: E402
from qualitylab.learn import concepts as C  # noqa: E402
from qualitylab.plotting import INK, INK_2, INK_3, SERIES, SERIES_2, _style  # noqa: E402


@st.cache_data(show_spinner=False)
def _synthetic(n: int) -> list[dict]:
    return RA.synthetic_events(n, seed=1)


st.title("🔒 Instructor & research dashboard")
cfg = research.load_config()


def _password() -> str:
    """Top-level ``instructor_password`` in the app's secrets (or the one inside ``[research]``)."""
    try:
        top = str(st.secrets.get("instructor_password", "") or "")
    except Exception:  # noqa: BLE001 - no secrets file at all
        top = ""
    return top or cfg.instructor_password


# ---- the whole page is locked: nothing below runs without the password ---------------------------
PASSWORD = _password()
if not PASSWORD:
    st.info("This page is for the course instructor and is locked. To use it, the app owner adds a line "
            "`instructor_password = \"...\"` at the top of the app's Secrets on share.streamlit.io.")
    st.stop()
if not st.session_state.get("instr_ok"):
    tries = st.session_state.get("instr_tries", 0)
    if tries >= 5:
        st.error("Too many wrong attempts. Close this tab and open the page again.")
        st.stop()
    with st.form("pw"):
        pw = st.text_input("Instructor password", type="password")
        if st.form_submit_button("Unlock", type="primary"):
            if hmac.compare_digest(pw.encode(), PASSWORD.encode()):
                st.session_state.instr_ok = True
                st.session_state.pop("instr_tries", None)
                st.rerun()
            else:
                st.session_state.instr_tries = tries + 1
                st.error("Wrong password.")
    st.stop()

if st.button("Lock this page"):
    st.session_state.instr_ok = False
    st.rerun()

with st.expander("Research configuration status", expanded=not cfg.active):
    if cfg.active:
        st.success(f"Research data collection is **on** · backend: {cfg.backend} · IRB protocol {cfg.irb_protocol} · "
                   f"course code {cfg.course_code or '(none)'} · conditions: {', '.join(cfg.conditions) or '(none)'}")
    elif cfg.enabled:
        st.error("Research is enabled but misconfigured, so **nothing is being collected**:\n\n- "
                 + "\n- ".join(cfg.problems()))
    else:
        st.info("Research data collection is **off** (no `[research]` section in the app's secrets, or "
                "`enabled = false`). Students can use the Learning Lab; nothing is stored. See "
                "`docs/research/SETUP.md` to turn it on after IRB approval.")

src = st.radio("Data source", ["Collected data", "Synthetic preview (fake data)"], horizontal=True,
               index=0 if cfg.active else 1,
               help="The synthetic preview shows what the dashboard will look like, using simulated students.")
if src.startswith("Collected"):
    if not cfg.active:
        st.warning("Research collection is not active, so there is no collected data.")
        st.stop()
    try:
        with st.spinner("Loading events…"):
            events = research.make_backend(cfg).read()
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not read data from the backend: {e}")
        st.stop()
else:
    n = st.slider("Synthetic students", 10, 200, 40, 10)
    events = _synthetic(n)
    st.warning("⚠️ **Synthetic data.** Every number below is simulated and must not be reported as a finding.")

if not events:
    st.info("No events yet.")
    st.stop()



@st.cache_data(show_spinner="Analysing…", max_entries=20)
def _tables(events: list[dict], pick: tuple[str, ...]):
    ev = RA.to_frame(events)
    ev = ev[ev["course_code"].isin(pick)]
    P = RA.participants(ev)
    return ev, RA.experiments(ev), P, RA.summary(P), RA.items(ev)


courses = sorted({e.get("course_code") or "" for e in events})
pick = st.multiselect("Course sections", courses, default=courses)
ev, X, P, S, I = _tables(events, tuple(pick))  # noqa: E741

c1, c2, c3, c4 = st.columns(4)
c1.metric("Participants", S["participants"])
cc = S.get("concept", {})
c2.metric("Concept check", f"{cc.get('mean_pre', np.nan):.0%} → {cc.get('mean_post', np.nan):.0%}" if cc.get("n", 0) >= 3 else "–",
          help="Mean share correct, participants with both checks.")
c3.metric("Class normalized gain ⟨g⟩", f"{cc.get('class_normalized_gain', np.nan):.2f}" if "class_normalized_gain" in cc else "–")
c4.metric("System Usability Scale", f"{S['sus_mean']:.0f}" if S.get("sus_mean") is not None else "–",
          help="0–100; about 68 is average across published studies.")

t0, t1, t2, t3, t4 = st.tabs(["Process Lab", "Learning", "Missions (class debrief)", "Feedback", "Data & export"])

with t0:
    if X.empty:
        st.info("No Process Lab experiments yet.")
    else:
        pls = S.get("processlab", {})
        a, b, c, d = st.columns(4)
        a.metric("Experiments", len(X), help="All runs, including re-runs with new random data.")
        b.metric("Per student (median)", f"{pls.get('experiments_median', np.nan):.0f}")
        ofs = pls.get("one_factor_share_mean")
        c.metric("Changed one setting at a time", "–" if ofs is None else f"{ofs:.0%}",
                 help="Share of a student's follow-up experiments that changed exactly one setting (a controlled "
                      "comparison), averaged over students.")
        d.metric("Students who replicated", f"{pls.get('replicated_share', np.nan):.0%}",
                 help="Used 'Run it 200 times' at least once.")
        lc = RA.experiment_learning_curve(X)
        if len(lc) >= 2 and lc.get("pred_detect_correct") is not None and lc["pred_detect_correct"].notna().any():
            fig, ax = plt.subplots(figsize=(9, 3.2))
            _style(ax)
            ax.plot(lc.index, lc["pred_detect_correct"], color=SERIES, lw=2.2, marker="o", label="predicted detection correctly")
            if "pred_delay_log_error" in lc and lc["pred_delay_log_error"].notna().any():
                ax2 = ax.twinx()
                ax2.plot(lc.index, lc["pred_delay_log_error"], color=SERIES_2, lw=2.2, marker="s",
                         label="delay prediction error |log(pred/actual)|")
                ax2.set_ylabel("delay error", color=SERIES_2)
                ax2.spines["top"].set_visible(False)
            ax.set_ylim(0, 1.05)
            ax.set_xlabel("experiment number (each student's 1st, 2nd, ...)", color=INK_2)
            ax.set_ylabel("share correct", color=SERIES)
            ax.set_title("Do predictions improve with experience?", loc="left", fontsize=11, fontweight="bold",
                         color=INK)
            st.pyplot(fig, width="stretch")
            plt.close(fig)
            st.caption("Students per point: " + ", ".join(f"#{k}: {v}" for k, v in lc["students"].items()))
        ch = pd.Series([c for v in X["changed"].dropna() for c in str(v).split(";") if c]).value_counts()
        a, b = st.columns(2)
        if len(ch):
            a.markdown("**Settings students changed most**")
            a.dataframe(ch.rename(lambda k: k.split(".")[-1]).rename("times").to_frame(), width="stretch")
        b.markdown("**Charts used**")
        b.dataframe(X["chart"].value_counts().rename("experiments").to_frame(), width="stretch")
        for k_, t_ in (("delay_error_first_vs_second_half", "delay prediction error"),
                       ("detect_accuracy_first_vs_second_half", "detection prediction accuracy")):
            tt = pls.get(k_, {})
            if tt.get("n", 0) >= 3:
                st.markdown(f"**{t_.capitalize()}, first vs. second half of each student's experiments** "
                            f"(paired, n = {tt['n']}): {tt['mean_pre']:.2f} → {tt['mean_post']:.2f}, "
                            f"t = {tt['t']:.2f}, p = {tt['p']:.3g}, d_z = {tt['cohens_dz']:.2f}.")

with t1:
    if cc.get("n", 0) >= 3:
        lo, hi = cc["mean_diff_ci95"]
        st.markdown(f"**Pre → post (paired, n = {cc['n']}):** mean change {cc['mean_diff'] * 100:+.1f} points "
                    f"(95 % CI {lo * 100:+.1f} to {hi * 100:+.1f}), t = {cc['t']:.2f}, "
                    f"p = {cc['p']:.3g}, Cohen's d_z = {cc['cohens_dz']:.2f} (Wilcoxon p = {cc['wilcoxon_p']:.3g}).")
    if "gain_by_condition" in S:
        st.markdown("**Gain by condition:** " + "; ".join(f"{k}: {v['mean']:+.1%} (n={v['n']})"
                                                         for k, v in S["gain_by_condition"].items())
                    + (f" · Welch t = {S['gain_condition_welch']['t']:.2f}, p = {S['gain_condition_welch']['p']:.3g} "
                       f"({S['gain_condition_welch']['comparison']})" if "gain_condition_welch" in S else ""))
        an = S.get("post_condition_ancova", {})
        if "estimate" in an:
            st.markdown(f"**ANCOVA** (final score on warm-up score and condition; {an['effect']}): "
                        f"{an['estimate'] * 100:+.1f} points, 95 % CI {an['ci95'][0] * 100:+.1f} to "
                        f"{an['ci95'][1] * 100:+.1f}, p = {an['p']:.3g} (n = {an['n']}).")
    cal = RA.calibration(ev)
    if len(cal) and {"correct", "incorrect"} <= set(cal.columns):
        st.markdown("**Confidence calibration** (mean confidence 1–5): " + "; ".join(
            f"{k}: {r['correct']:.2f} when right vs. {r['incorrect']:.2f} when wrong" for k, r in cal.iterrows()))
    if not I.empty and I["pre_n"].notna().any():
        fig, ax = plt.subplots(figsize=(10, 4.2))
        _style(ax)
        y = np.arange(len(I))[::-1]
        ax.barh(y + 0.2, I["pre_correct"].fillna(0), height=0.38, color=INK_3, label="Warm-up")
        ax.barh(y - 0.2, I["post_correct"].fillna(0), height=0.38, color=SERIES, label="Final")
        ax.set_yticks(y)
        ax.set_yticklabels(I["concept"], fontsize=8, color=INK)
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.legend(frameon=False, fontsize=8, loc="lower right", labelcolor=INK_2)
        ax.set_title("Share correct by concept", loc="left", fontsize=11, fontweight="bold", color=INK)
        st.pyplot(fig, width="stretch")
        plt.close(fig)
        st.caption("Concepts where the final share is still low are good candidates for a class discussion.")

with t2:
    st.caption("Use these anonymous, class-level results to debrief the missions in class.")

    def pct(col):
        v = P[col].dropna() if col in P else pd.Series(dtype=float)
        return f"{v.mean():.0%} (n={len(v)})" if len(v) else "–"

    st.markdown(f"""
| Mission | Class result |
|---|---|
| 🔴 Red Bead Factory | blamed the system, not the workers: **{pct('rb_system_cause')}** · chose the supplier fix: **{pct('rb_chose_supplier')}** · rewarded/warned/fired on **{pct('rb_blame_index')}** of worker-days |
| 📡 Signal or Noise? | d′ round 1 → round 2: **{P['sig_dprime_A'].mean():.2f} → {P['sig_dprime_B'].mean():.2f}** |
| 🎯 Tampering Trap | adjusted on **{pct('fn_share_adjusted')}** of fills · error vs. leaving it alone: **×{P['fn_sd_ratio'].mean():.2f}** · barista question correct: **{pct('fn_check_correct')}** |
| 📏 Keep the Customer | found the cheapest way to Cpk ≥ 1.33: **{pct('cap_found_cheapest')}** · sorting task: **{P['cap_sort_score'].mean():.1f}/8** |
| 💰 Where Does the Money Go? | cost-of-quality sort: **{P['pg_coq_score'].mean():.0%}** · best portfolio found: **{P['pg_best_share_of_optimal'].mean():.0%} of optimal** |
| 🧭 Be the Quality Manager | regret on first attempt **{P['mg_first_regret_pct'].mean():.0%}** → best attempt **{P['mg_best_regret_pct'].mean():.0%}** above the best plan |
""".replace("nan", "–"))
    rb = RA.redbeads_debrief(ev)
    if rb:
        st.markdown(
            f"**🔴 Red beads, the worker with the most red beads on Day 1:** {rb['acted_on_worst']:.0%} of the class "
            f"warned, fired or otherwise acted on that worker ("
            + ", ".join(f"{k.lower()} {v}" for k, v in rb["worst_actions"].items())
            + f"). That worker averaged **{rb['worst_day1']:.1f}** red beads on Day 1 and **{rb['worst_day2']:.1f}** on "
            f"Day 2, and the best worker went from **{rb['best_day1']:.1f}** to **{rb['best_day2']:.1f}**, whatever "
            "the manager did: regression to the mean (the expected value is 10 for everyone).")
    sc = RA.signals_by_category(ev)
    if not sc.empty:
        st.markdown("**📡 Signal or Noise: share of charts the class investigated**, by kind of chart. "
                    "High numbers on noise are false alarms; low numbers on signals are misses.")
        st.dataframe(sc.style.format("{:.0%}", na_rep="–"), width="content")
    if P[["sig_dprime_A", "sig_dprime_B"]].notna().all(axis=1).sum() >= 3:
        fig, ax = plt.subplots(figsize=(7, 3.2))
        _style(ax)
        both = P.dropna(subset=["sig_dprime_A", "sig_dprime_B"])
        for _, r in both.iterrows():
            ax.plot([0, 1], [r["sig_dprime_A"], r["sig_dprime_B"]], color=INK_3, lw=0.8, alpha=0.5)
        ax.plot([0, 1], [both["sig_dprime_A"].mean(), both["sig_dprime_B"].mean()], color=SERIES_2, lw=3, marker="o")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Round 1 (instinct)", "Round 2 (with the rules)"])
        ax.set_ylabel("d′", color=INK_2)
        ax.set_title("Signal or Noise? Each line is one student", loc="left", fontsize=11, fontweight="bold", color=INK)
        st.pyplot(fig, width="stretch")
        plt.close(fig)

with t3:
    lk = [k for k, _ in C.LEARNING_ITEMS if k in P]
    if lk and P[lk].notna().any().any():
        tab = pd.DataFrame({"Statement": [t for k, t in C.LEARNING_ITEMS if k in lk],
                            "Mean (1–5)": [P[k].mean() for k in lk],
                            "Agree or strongly agree": [(P[k] >= 4).mean() for k in lk]})
        st.dataframe(tab.style.format({"Mean (1–5)": "{:.2f}", "Agree or strongly agree": "{:.0%}"}),
                     width="stretch", hide_index=True)
    txt = ev[(ev["event_type"] == "text") & (ev["mission"] == "survey")]
    if len(txt):
        st.markdown("**Open comments**")
        for item, g in txt.groupby("item_id"):
            st.markdown(f"*{'Most helpful' if item == 'most_helpful' else 'Could be better'}*")
            for v in g["response"].head(30):
                st.text(f"“{RA._resp(v) or ''}”")  # shown as plain text: no markdown or links from students

with t4:
    st.markdown("Downloads are **anonymous**: participant codes are one-way hashes. Store them only where your IRB "
                "protocol allows.")
    a, b, c, d = st.columns(4)
    a.download_button("Events (CSV)", ev.to_csv(index=False).encode(), "learning_lab_events.csv", "text/csv")
    b.download_button("Participants (CSV)", P.to_csv().encode(), "learning_lab_participants.csv", "text/csv")
    d.download_button("Experiments (CSV)", X.to_csv(index=False).encode(), "process_lab_experiments.csv", "text/csv",
                      help="One row per Process Lab experiment: design, prediction, outcome.")
    xb = io.BytesIO()
    with pd.ExcelWriter(xb, engine="openpyxl") as xw:
        P.assign(first_seen=P["first_seen"].astype(str), last_seen=P["last_seen"].astype(str)).to_excel(
            xw, sheet_name="participants")
        I.to_excel(xw, sheet_name="concept_items")
        X.assign(ts_utc=X["ts_utc"].astype(str)).to_excel(xw, sheet_name="experiments", index=False)
        ev.assign(ts_utc=ev["ts_utc"].astype(str)).to_excel(xw, sheet_name="events", index=False)
        pd.DataFrame([{"key": k, "value": json.dumps(v, default=str)} for k, v in S.items()]).to_excel(
            xw, sheet_name="summary", index=False)
    c.download_button("Everything (Excel)", xb.getvalue(), "learning_lab_data.xlsx")
    st.markdown("**Withdrawal.** If a student asks to withdraw, they give you their research code (shown in the "
                "Learning Lab sidebar). Delete their rows from the data store, and filter them out here:")
    rm = st.text_input("Participant codes to exclude (comma-separated)")
    if rm.strip():
        drop = {x.strip().upper() for x in rm.split(",") if x.strip()}
        st.write(f"Would exclude {P.index.isin(drop).sum()} participant(s). Delete them in the source data as well.")
    st.dataframe(P.reset_index(), width="stretch", height=300)
