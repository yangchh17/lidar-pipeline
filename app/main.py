"""LiDAR Processing Pipeline — Streamlit GUI."""

import streamlit as st

st.set_page_config(
    page_title="LiDAR Pipeline",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.components.sidebar import render_sidebar
from app.components.runner import render_runner
from app.components.results import render_results

# ── Session state defaults ──
if "run_state" not in st.session_state:
    st.session_state.run_state = "idle"  # idle | running | done | error
if "run_result" not in st.session_state:
    st.session_state.run_result = None

# ── Header ──
st.title("🏔️ LiDAR Processing Pipeline")
st.caption("Automated terrain processing — DTM, DSM, and hillshade from LAS/LAZ tiles")

# ── Sidebar: parameters ──
params = render_sidebar()

# ── Main area ──
tab_run, tab_results = st.tabs(["▶ Run Pipeline", "📊 Results"])

with tab_run:
    render_runner(params)

with tab_results:
    render_results(params)
