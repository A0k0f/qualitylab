"""Landing page."""
from __future__ import annotations

import streamlit as st

st.title("QualityLab")
st.markdown(
    "#### Decide how to watch a process, before problems reach your customers.\n"
    "Every operation has the same nagging questions: *How often should we check? Is that audit catching "
    "anything? Should we inspect everything, sample, or neither? Is a new machine worth it?* "
    "QualityLab answers them with numbers you can take to a meeting."
)

with st.container(border=True):
    st.markdown("### 🎓 Learning Lab")
    st.markdown(
        "**For students.** Six short, game-like missions that put you in a manager's seat: run Deming's Red Bead "
        "factory, call signal or noise on business charts, try to out-adjust a filling machine, save a contract "
        "that needs Cpk ≥ 1.33, spend an improvement budget, and design an inspection plan. Each one asks you to "
        "**predict, decide, see the result and explain it**, with a warm-up and final check to show what you learned.")
    st.page_link("views/learning_lab.py", label="Open the Learning Lab", icon="➡️")

a, b = st.columns(2)
with a, st.container(border=True):
    st.markdown("### 🧭 Decision Studio")
    st.markdown(
        "**For managers and owners.** Describe your process in plain terms: volume, what goes wrong, what "
        "mistakes cost, and how you check today. The simulator replays years of operation under hundreds of "
        "monitoring and inspection plans and tells you:\n"
        "- the **cheapest plan that meets your limits** (and a simpler one that is almost as cheap)\n"
        "- **how much you save**, with a realistic range\n"
        "- how fast problems get caught, how many defects still escape, how many false alarms to expect\n"
        "- whether the answer **holds up** if your estimates are off\n"
        "- where to **aim** the process, and whether an **investment** pays back"
    )
    st.page_link("views/decision_studio.py", label="Open Decision Studio", icon="➡️")
    st.caption("Six editable starting scenarios: beverage filling, CNC machining, warehouse picking, pharmacy "
               "dispensing, invoice processing, supplier lots.")
with b, st.container(border=True):
    st.markdown("### 📈 SPC Toolkit")
    st.markdown(
        "**For analysts, engineers and classes.** Upload data or open a practice scenario and get the right "
        "control chart with a plain-language reading:\n"
        "- X̄-R, X̄-S, I-MR, p, np, c, u (with Laney), EWMA, CUSUM, Hotelling T²\n"
        "- all 8 run rules, Phase I/II limits\n"
        "- capability (Cp, Cpk, Pp, Ppk with confidence intervals) and Pareto\n"
        "- a simulator showing which chart catches shifts fastest\n"
        "- personal dataset codes for classroom labs"
    )
    st.page_link("views/spc_toolkit.py", label="Open SPC Toolkit", icon="➡️")

st.divider()
st.markdown(
    "**How the Decision Studio works.** It is a Monte Carlo simulation: a model of your process runs through "
    "many simulated years, problems strike at random at the rates you give, and each plan is scored on its "
    "full cost: checking, false alarms, fixes, scrap, inspection, overfill and defects that reach customers. "
    "The numbers are only as good as the inputs, so the studio also shows how the answer changes if your "
    "estimates are off."
)
st.caption("QualityLab is open source (MIT). Nothing you type or upload is stored.")
