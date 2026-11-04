"""Shared state, logging and layout helpers for the Learning Lab."""
from __future__ import annotations

import io
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from qualitylab import research, teaching  # noqa: E402

MISSIONS = {
    "redbeads": dict(title="The Red Bead Factory", icon="🔴", minutes=12,
                     topic="Deming's philosophy · the system vs. the worker",
                     hook="You manage six workers. Some make more defects than others. Who do you reward, warn or fire?"),
    "signals": dict(title="Signal or Noise?", icon="📡", minutes=15,
                    topic="Common vs. special causes · control-chart rules",
                    hook="Sixteen charts from eight businesses. Investigate or leave it alone? Every call costs money."),
    "funnel": dict(title="The Tampering Trap", icon="🎯", minutes=10,
                   topic="Deming's funnel · over-adjustment",
                   hook="Run a filling machine yourself. Can you beat a machine that is left alone?"),
    "capability": dict(title="Keep the Customer", icon="📏", minutes=12,
                       topic="Control vs. specification limits · Cp and Cpk",
                       hook="Your biggest customer demands Cpk ≥ 1.33. Find the cheapest way to deliver it."),
    "pareto": dict(title="Where Does the Money Go?", icon="💰", minutes=12,
                   topic="Cost of quality · Pareto analysis · project selection",
                   hook="You have $40,000 to cut complaint costs. Which projects do you fund?"),
    "manager": dict(title="Be the Quality Manager", icon="🧭", minutes=10,
                    topic="Decision-making for quality · economics of monitoring",
                    hook="Design the inspection plan for a bottling line and see what it costs over a year."),
    "processlab": dict(title="Process Lab", icon="🧪", minutes=30,
                       topic="Your own experiments · SPC, monitoring design, cost of quality",
                       hook="Set up any process, decide what goes wrong, choose how to watch it, predict, run."),
}
ORDER = list(MISSIONS)
GUIDED = [k for k in ORDER if k != "processlab"]  # the six guided missions


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------

def lab() -> dict:
    if "lab" not in st.session_state:
        st.session_state.lab = dict(
            session_id=research.new_session_id(),
            consent=None,          # None = not asked yet, True / False after the choice
            pid="", condition="",
            seed=int(np.random.default_rng().integers(1, 2**31 - 1)),
            view="home",
            record=[],             # every event, for the student's own learning record
            done={}, started={},
            m={},                  # per-mission state
            pre=None, post=None, survey=None,
            student="",            # name typed for the participation record (teaching use only)
            shown={},
        )
    return st.session_state.lab


def cfg() -> research.ResearchConfig:
    if "lab_cfg" not in st.session_state:
        st.session_state.lab_cfg = research.load_config()
    return st.session_state.lab_cfg


def tcfg() -> teaching.TeachingConfig:
    if "lab_tcfg" not in st.session_state:
        st.session_state.lab_tcfg = teaching.load_config()
    return st.session_state.lab_tcfg


def recording_participation() -> bool:
    return tcfg().active and bool(lab()["student"])


def collecting() -> bool:
    return cfg().active and lab()["consent"] is True and bool(lab()["pid"])


def ask_predictions() -> bool:
    """Experimental condition hook: 'no_predict' skips the prediction steps."""
    return lab()["condition"] != "no_predict"


def mstate(mission: str) -> dict:
    s = lab()["m"]
    if mission not in s:
        s[mission] = {"step": 0}
    return s[mission]


def go(view: str) -> None:
    lab()["view"] = view
    st.rerun()


def seed_for(mission: str, k: int = 0) -> int:
    return (lab()["seed"] * 1_000_003 + ORDER.index(mission) * 97 + k) % (2**31 - 1) if mission in ORDER \
        else (lab()["seed"] + k) % (2**31 - 1)


# ---------------------------------------------------------------------------
# timing and logging
# ---------------------------------------------------------------------------

def shown(key: str) -> None:
    lab()["shown"].setdefault(key, time.time())


def elapsed(key: str) -> float | None:
    t = lab()["shown"].get(key)
    return None if t is None else time.time() - t


def log(mission: str, step: str, event_type: str, *, timer: str | None = None, **kw) -> dict:
    L = lab()
    ev = research.make_event(session_id=L["session_id"], participant_id=L["pid"], condition=L["condition"],
                             course_code=cfg().course_code, mission=mission, step=step, event_type=event_type,
                             latency_s=elapsed(timer) if timer else kw.pop("latency_s", None), **kw)
    L["record"].append(ev)
    if collecting():
        sink = research.get_sink(cfg())
        sink.submit([ev])
        if event_type == "complete" and sink.pending:
            sink.flush(wait=False)  # retry anything a network hiccup held back, without making the student wait
    if recording_participation():  # separate store, with the name and without the research code or condition
        tsink = teaching.get_sink(tcfg())
        tsink.submit([teaching.to_teaching_event(ev, L["student"], tcfg())])
        if event_type == "complete" and tsink.pending:
            tsink.flush(wait=False)
    return ev


def start_mission(mission: str) -> None:
    L = lab()
    if mission not in L["started"]:
        L["started"][mission] = time.time()
        log(mission, "start", "start")


def complete_mission(mission: str, summary: dict) -> None:
    L = lab()
    if mission in L["done"]:
        return
    dur = time.time() - L["started"].get(mission, time.time())
    L["done"][mission] = summary
    log(mission, "end", "complete", score=summary.get("score"), response=summary, latency_s=dur)


# ---------------------------------------------------------------------------
# layout helpers
# ---------------------------------------------------------------------------

def esc(text: str) -> str:
    return str(text).replace("$", r"\$")


def _box_text(text: str) -> str:
    """Markdown-ish text for an HTML callout: **bold** → <b>, dollar signs escaped."""
    import html
    import re

    t = html.escape(str(text), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", t)
    return t.replace("$", "&#36;")


def show(fig) -> None:
    st.pyplot(fig, width="stretch")
    plt.close(fig)


def fig_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def header(mission: str, step: int, steps: list[str]) -> None:
    m = MISSIONS[mission]
    c1, c2 = st.columns([5, 1])
    c1.markdown(f"### {m['icon']} {m['title']}")
    c1.caption(m["topic"])
    if c2.button("← All missions", key=f"back_{mission}_{step}"):
        go("home")
    st.progress(min(1.0, step / max(1, len(steps) - 1)),
                text=f"Step {min(step + 1, len(steps))} of {len(steps)}: {steps[min(step, len(steps) - 1)]}")


def confidence(key: str, label: str = "How confident are you?") -> int:
    return st.select_slider(label, options=[1, 2, 3, 4, 5], value=3, key=key,
                            format_func=lambda v: {1: "1 · guessing", 2: "2", 3: "3", 4: "4", 5: "5 · certain"}[v])


def predict_box(text: str):
    st.markdown(
        f"<div style='border-left:4px solid #eb6834;background:rgba(235,104,52,.08);padding:10px 14px;"
        f"border-radius:6px;margin:6px 0 10px'><b>🔮 Predict first.</b> {_box_text(text)}</div>", unsafe_allow_html=True)


def insight(text: str):
    st.markdown(
        f"<div style='border-left:4px solid #2a78d6;background:rgba(42,120,214,.08);padding:10px 14px;"
        f"border-radius:6px;margin:6px 0 10px'>💡 {_box_text(text)}</div>", unsafe_allow_html=True)


def no_names_hint() -> None:
    st.caption("Please don't include names or other identifying details in your answer.")
