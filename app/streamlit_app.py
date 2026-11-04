"""QualityLab web app.

Run locally:   streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# make the package importable without installation (e.g. on Streamlit Community Cloud)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _fresh_code() -> None:
    """After a push, Streamlit Cloud re-runs the pages but keeps already-imported modules in memory, so
    pages could call functions that the old modules don't have. If any of our source files changed since
    they were imported, drop those modules so they load again from the new files."""
    files = list((ROOT / "src" / "qualitylab").rglob("*.py")) + list((ROOT / "app" / "lablib").glob("*.py"))
    stamp = max((f.stat().st_mtime_ns for f in files), default=0), len(files)
    if getattr(sys, "_qualitylab_stamp", None) not in (None, stamp):
        for name in [m for m in sys.modules if m == "qualitylab" or m.startswith(("qualitylab.", "lablib"))]:
            del sys.modules[name]
    sys._qualitylab_stamp = stamp


_fresh_code()

st.set_page_config(page_title="QualityLab", page_icon="📈", layout="wide")

VIEWS = Path(__file__).resolve().parent / "views"
home = st.Page(str(VIEWS / "home.py"), title="Home", icon="🏠", default=True)
studio = st.Page(str(VIEWS / "decision_studio.py"), title="Decision Studio", icon="🧭", url_path="decision-studio")
toolkit = st.Page(str(VIEWS / "spc_toolkit.py"), title="SPC Toolkit", icon="📈", url_path="toolkit")
learn = st.Page(str(VIEWS / "learning_lab.py"), title="Learning Lab", icon="🎓", url_path="learn")
instructor = st.Page(str(VIEWS / "instructor.py"), title="Instructor dashboard", icon="🔒", url_path="instructor")

st.sidebar.markdown("### 📈 QualityLab")
nav = st.navigation({"": [home], "For students": [learn], "For managers": [studio],
                     "For analysts & classes": [toolkit, instructor]})
nav.run()
