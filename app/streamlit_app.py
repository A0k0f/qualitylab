"""QualityLab web app.

Run locally:   streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# make the package importable without installation (e.g. on Streamlit Community Cloud)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

st.set_page_config(page_title="QualityLab", page_icon="📈", layout="wide")

VIEWS = Path(__file__).resolve().parent / "views"
home = st.Page(str(VIEWS / "home.py"), title="Home", icon="🏠", default=True)
studio = st.Page(str(VIEWS / "decision_studio.py"), title="Decision Studio", icon="🧭", url_path="decision-studio")
toolkit = st.Page(str(VIEWS / "spc_toolkit.py"), title="SPC Toolkit", icon="📈", url_path="toolkit")

st.sidebar.markdown("### 📈 QualityLab")
nav = st.navigation({"": [home], "For managers": [studio], "For analysts & classes": [toolkit]})
nav.run()
