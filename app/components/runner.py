"""Run tab — validation, execution, and live progress."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import streamlit as st

from app.components.sidebar import PipelineParams
from lidar_pipeline.validators import validate_inputs
from lidar_pipeline.runner import build_command
from lidar_pipeline.progress import LogParser


def _run_in_thread(cmd: list[str], status_container, log_container):
    """Execute the R pipeline in a background thread, streaming output."""
    parser = LogParser()
    lines: list[str] = []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            parser.feed(line)
            lines.append(line.rstrip())

        proc.wait()

        st.session_state.run_result = {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "elapsed_minutes": parser.status.elapsed_minutes,
            "errors": parser.status.errors,
            "warnings": parser.status.warnings,
            "log": lines,
        }
        st.session_state.run_state = "done" if proc.returncode == 0 else "error"

    except Exception as exc:
        st.session_state.run_result = {
            "success": False,
            "exit_code": -1,
            "elapsed_minutes": 0,
            "errors": [str(exc)],
            "warnings": [],
            "log": lines,
        }
        st.session_state.run_state = "error"


def render_runner(params: PipelineParams):
    """Render the Run Pipeline tab."""

    # ── Input validation summary ──
    if not params.input_dir:
        st.info("👈 Set an input directory in the sidebar to get started.")
        return

    if not params.input_valid:
        st.error(f"Input directory not found: `{params.input_dir}`")
        return

    if not params.has_las_files:
        st.warning(f"No LAS/LAZ files found in `{params.input_dir}`")
        return

    if not params.output_dir:
        st.warning("Set an output directory in the sidebar.")
        return

    # ── Pre-flight validation ──
    with st.spinner("Validating inputs..."):
        result = validate_inputs(
            input_dir=params.input_dir,
            output_dir=params.output_dir,
            resolution=params.resolution,
            cores=params.cores,
            csf_rigidness=params.csf_rigidness,
        )

    # Show validation results
    col1, col2, col3 = st.columns(3)
    col1.metric("Tiles", result.file_count)
    col2.metric("Points", f"{result.total_points:,}")
    col3.metric("Size", f"{result.total_size_mb:.1f} MB")

    for w in result.warnings:
        st.warning(w)
        # Friendly suggestions for common warnings
        if "CRS" in w or "crs" in w:
            st.info("💡 Tip: Reproject all tiles to a single CRS (e.g. using `las2las` or PDAL) before processing.")
        if "disk space" in w.lower() or "Low disk" in w:
            st.info("💡 Tip: Free up disk space or reduce resolution to shrink output size.")
        if "RAM" in w or "memory" in w.lower():
            st.info("💡 Tip: Try reducing chunk size or number of cores to lower memory usage.")

    if not result.ok:
        for e in result.errors:
            st.error(e)
            # Friendly suggestions for common errors
            if "Resolution" in e:
                st.info("💡 Resolution must be a positive number (e.g. 0.5 for 50cm cells).")
            if "rigidness" in e:
                st.info("💡 CSF rigidness should be 1 (flat), 2 (moderate), or 3 (steep terrain).")
            if "Cannot read" in e:
                st.info("💡 One or more LAS files may be corrupted. Try removing the bad file and re-running.")
        return

    st.success("✓ Inputs validated — ready to process")

    # ── Run / status ──
    run_state = st.session_state.run_state

    if run_state == "idle":
        col_run, col_dry = st.columns([1, 1])
        with col_run:
            if st.button("🚀 Run Pipeline", type="primary", use_container_width=True):
                Path(params.output_dir).mkdir(parents=True, exist_ok=True)
                cmd = build_command(
                    params.input_dir,
                    params.output_dir,
                    resolution=params.resolution,
                    csf_cloth_res=params.csf_cloth_res,
                    csf_threshold=params.csf_threshold,
                    csf_rigidness=params.csf_rigidness,
                    chunk_size=params.chunk_size,
                    chunk_buffer=params.chunk_buffer,
                    cores=params.cores,
                    hillshade_angle=params.hillshade_angle,
                    hillshade_direction=params.hillshade_direction,
                    skip_dtm=params.skip_dtm,
                    skip_dsm=params.skip_dsm,
                    skip_hillshade=params.skip_hillshade,
                    resume=params.resume,
                    verbose=params.verbose,
                )
                st.session_state.run_state = "running"
                st.session_state.run_cmd = cmd
                thread = threading.Thread(
                    target=_run_in_thread,
                    args=(cmd, None, None),
                    daemon=True,
                )
                thread.start()
                st.rerun()

        with col_dry:
            if st.button("🔍 Dry Run", use_container_width=True):
                st.info("Dry run — validation passed, no processing performed.")

    elif run_state == "running":
        st.info("⏳ Pipeline is running... This page will update when complete.")
        if st.button("🔄 Refresh"):
            st.rerun()

    elif run_state in ("done", "error"):
        outcome = st.session_state.run_result
        if outcome and outcome["success"]:
            st.success(f"✓ Pipeline complete ({outcome['elapsed_minutes']:.1f} min)")
        elif outcome:
            st.error(f"✗ Pipeline failed (exit code {outcome['exit_code']})")
            for err in outcome["errors"]:
                st.error(err)
            # Suggest common fixes
            if outcome["exit_code"] == 1:
                st.info(
                    "💡 Common causes: missing R packages, bad file paths, or out-of-memory. "
                    "Check the full log below for details."
                )
            if any("Rscript" in e or "not found" in e for e in outcome.get("errors", [])):
                st.info(
                    "💡 R doesn't seem to be installed or isn't on PATH. "
                    "Install R from https://cran.r-project.org/ and make sure `Rscript` is accessible."
                )

        if outcome and outcome.get("warnings"):
            with st.expander(f"⚠ {len(outcome['warnings'])} warning(s)"):
                for w in outcome["warnings"]:
                    st.warning(w)

        if outcome and outcome.get("log"):
            with st.expander("📋 Full log", expanded=False):
                st.code("\n".join(outcome["log"]), language="text")

        if st.button("🔄 New Run"):
            st.session_state.run_state = "idle"
            st.session_state.run_result = None
            st.rerun()
