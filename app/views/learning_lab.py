"""Learning Lab page: the Process Lab and guided missions for students, with optional consent-based research logging."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lablib import home, m_capability, m_funnel, m_manager, m_pareto, m_processlab, m_redbeads, m_signals  # noqa: E402,I001
from lablib.core import GUIDED, MISSIONS, cfg, collecting, go, lab  # noqa: E402

PAGES = {"processlab": m_processlab.run, "redbeads": m_redbeads.run, "signals": m_signals.run, "funnel": m_funnel.run,
         "capability": m_capability.run, "pareto": m_pareto.run, "manager": m_manager.run}

L = lab()

# sidebar: progress and record
with st.sidebar:
    st.markdown("**Learning Lab progress**")
    marks = []
    marks.append(("✅" if L["pre"] else "⬜") + " Warm-up check")
    n_exp = len(L["m"].get("processlab", {}).get("history", []))
    marks.append(("✅" if "processlab" in L["done"] else ("▶️" if n_exp else "⬜"))
                 + f" Process Lab{f' ({n_exp} runs)' if n_exp else ''}")
    for k in GUIDED:
        marks.append(("✅" if k in L["done"] else ("▶️" if k in L["m"] else "⬜")) + f" {MISSIONS[k]['title']}")
    marks.append(("✅" if L["post"] else "⬜") + " Final check")
    st.markdown("  \n".join(marks))
    if L["view"] != "home" and st.button("🏠 Learning Lab home", width="stretch"):
        go("home")
    if collecting():
        st.caption(f"Research code: {L['pid']}")

# consent gate (only when the deployment is configured for an approved study)
if cfg().active and L["consent"] is None:
    if st.session_state.get("consent_step") == "code":
        home.code_view()
    else:
        home.consent_view()
    st.stop()

view = L["view"]
if view == "home":
    home.home_view()
elif view in ("pre", "post"):
    home.check_view(view)
elif view == "survey":
    home.survey_view()
elif view in PAGES:
    PAGES[view]()
else:
    go("home")
