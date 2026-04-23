"""Sidebar — input paths and processing parameters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import streamlit as st


PRESETS = {
    "⚡ Fast": {"resolution": 1.0, "csf_rigidness": 1, "cores": 4, "chunk_size": 500},
    "⚖️ Balanced": {"resolution": 0.5, "csf_rigidness": 2, "cores": 2, "chunk_size": 250},
    "🎯 Accurate": {"resolution": 0.25, "csf_rigidness": 3, "cores": 1, "chunk_size": 150},
}


@dataclass
class PipelineParams:
    input_dir: str
    output_dir: str
    resolution: float
    csf_cloth_res: float
    csf_threshold: float
    csf_rigidness: int
    chunk_size: int
    chunk_buffer: int
    cores: int
    hillshade_angle: float
    hillshade_direction: float
    skip_dtm: bool
    skip_dsm: bool
    skip_hillshade: bool
    resume: bool
    verbose: bool

    @property
    def input_valid(self) -> bool:
        return bool(self.input_dir) and Path(self.input_dir).is_dir()

    @property
    def has_las_files(self) -> bool:
        if not self.input_valid:
            return False
        p = Path(self.input_dir)
        return any(p.glob("*.las")) or any(p.glob("*.laz")) or any(p.glob("*.LAS")) or any(p.glob("*.LAZ"))


def render_sidebar() -> PipelineParams:
    """Render the sidebar and return current parameters."""
    with st.sidebar:
        st.header("📂 Paths")
        input_dir = st.text_input(
            "Input directory",
            placeholder="C:\\data\\tiles",
            help="Folder containing LAS/LAZ point cloud tiles",
        )
        output_dir = st.text_input(
            "Output directory",
            placeholder="C:\\data\\results",
            help="Where to write DTM, DSM, hillshade outputs",
        )

        st.divider()

        # ── Presets ──
        st.header("⚙️ Parameters")
        preset = st.selectbox("Preset", list(PRESETS.keys()), index=1)
        defaults = PRESETS[preset]

        advanced = st.toggle("Advanced mode", value=False)

        # ── Core params (always visible) ──
        resolution = st.number_input(
            "Resolution (m)",
            min_value=0.1,
            max_value=10.0,
            value=defaults["resolution"],
            step=0.1,
            help="Output raster cell size in metres. Smaller = more detail but slower.",
        )
        cores = st.slider(
            "CPU cores",
            min_value=1,
            max_value=16,
            value=defaults["cores"],
            help="Parallel processing threads. More cores = faster but uses more RAM.",
        )

        # ── Advanced params ──
        if advanced:
            st.subheader("CSF Ground Classification")
            csf_cloth_res = st.number_input(
                "Cloth resolution",
                min_value=0.1, max_value=5.0, value=0.6, step=0.1,
                help="Resolution of the virtual cloth. Smaller = more detail.",
            )
            csf_threshold = st.number_input(
                "Classification threshold",
                min_value=0.1, max_value=2.0, value=0.4, step=0.1,
                help="Distance threshold for ground/non-ground classification.",
            )
            csf_rigidness = st.select_slider(
                "Terrain rigidness",
                options=[1, 2, 3],
                value=defaults["csf_rigidness"],
                format_func=lambda x: {1: "1 — Flat", 2: "2 — Moderate", 3: "3 — Steep"}[x],
                help="1 for flat terrain, 3 for steep/mountainous.",
            )

            st.subheader("Chunking")
            chunk_size = st.number_input(
                "Chunk size (m)", min_value=50, max_value=2000,
                value=defaults["chunk_size"], step=50,
                help="Processing tile size in metres.",
            )
            chunk_buffer = st.number_input(
                "Chunk buffer (m)", min_value=10, max_value=200, value=50, step=10,
                help="Overlap buffer to avoid edge artifacts.",
            )

            st.subheader("Hillshade")
            hillshade_angle = st.slider(
                "Sun elevation (°)", min_value=5, max_value=90, value=40,
                help="Sun angle above horizon.",
            )
            hillshade_direction = st.slider(
                "Sun azimuth (°)", min_value=0, max_value=360, value=270,
                help="Sun direction (0=N, 90=E, 180=S, 270=W).",
            )
        else:
            csf_cloth_res = 0.6
            csf_threshold = 0.4
            csf_rigidness = defaults["csf_rigidness"]
            chunk_size = defaults["chunk_size"]
            chunk_buffer = 50
            hillshade_angle = 40.0
            hillshade_direction = 270.0

        st.divider()

        # ── Output toggles ──
        st.header("📤 Outputs")
        col1, col2, col3 = st.columns(3)
        skip_dtm = col1.checkbox("Skip DTM")
        skip_dsm = col2.checkbox("Skip DSM")
        skip_hillshade = col3.checkbox("Skip Hillshade")

        st.divider()

        # ── Options ──
        resume = st.checkbox("Resume from checkpoint", help="Skip already-processed tiles.")
        verbose = st.checkbox("Verbose logging")

    return PipelineParams(
        input_dir=input_dir,
        output_dir=output_dir,
        resolution=resolution,
        csf_cloth_res=csf_cloth_res,
        csf_threshold=csf_threshold,
        csf_rigidness=csf_rigidness,
        chunk_size=chunk_size,
        chunk_buffer=chunk_buffer,
        cores=cores,
        hillshade_angle=hillshade_angle,
        hillshade_direction=hillshade_direction,
        skip_dtm=skip_dtm,
        skip_dsm=skip_dsm,
        skip_hillshade=skip_hillshade,
        resume=resume,
        verbose=verbose,
    )
