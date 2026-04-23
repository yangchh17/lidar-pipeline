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
from app.components.batch import render_batch_panel

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
tab_run, tab_results, tab_batch = st.tabs(["▶ Run Pipeline", "📊 Results", "📋 Batch"])

with tab_run:
    render_runner(params)

with tab_results:
    render_results(params)

with tab_batch:
    params_dict = {
        "input_dir": params.input_dir,
        "output_dir": params.output_dir,
        "resolution": params.resolution,
        "csf_cloth_res": params.csf_cloth_res,
        "csf_threshold": params.csf_threshold,
        "csf_rigidness": params.csf_rigidness,
        "chunk_size": params.chunk_size,
        "chunk_buffer": params.chunk_buffer,
        "cores": params.cores,
        "hillshade_angle": params.hillshade_angle,
        "hillshade_direction": params.hillshade_direction,
        "skip_dtm": params.skip_dtm,
        "skip_dsm": params.skip_dsm,
        "skip_hillshade": params.skip_hillshade,
        "resume": params.resume,
        "verbose": params.verbose,
    }
    render_batch_panel(params_dict)
