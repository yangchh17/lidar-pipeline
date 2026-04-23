"""Results tab — visualization and downloads."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app.components.sidebar import PipelineParams

try:
    import rasterio
    import numpy as np

    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False


def _find_outputs(output_dir: str) -> dict[str, Path | None]:
    """Locate expected pipeline output files."""
    p = Path(output_dir)
    return {
        "dtm": next(p.glob("dtm.tif"), None),
        "dsm": next(p.glob("dsm.tif"), None),
        "hillshade": next(p.glob("hillshade.tif"), None),
        "qa_report": next(p.glob("qa_report.html"), None),
        "qa_metrics": next(p.glob("qa_metrics.json"), None),
        "hillshade_preview": next(p.glob("dtm_hillshade.png"), None),
    }


def _render_qa_metrics(metrics_path: Path):
    """Display QA metrics from the JSON report."""
    with open(metrics_path) as f:
        metrics = json.load(f)

    st.subheader("📈 QA Metrics")

    if isinstance(metrics, dict):
        # Pipeline-level stats
        if "processing_time_minutes" in metrics:
            st.metric("Processing time", f"{metrics['processing_time_minutes']:.1f} min")

        # Tile-level stats
        tiles = metrics.get("tiles", metrics.get("tile_metrics", []))
        if tiles and isinstance(tiles, list):
            col1, col2 = st.columns(2)
            col1.metric("Tiles processed", len(tiles))
            total_pts = sum(t.get("point_count", t.get("raw_points", 0)) for t in tiles)
            col2.metric("Total points", f"{total_pts:,}")

        # Elevation stats
        elev = metrics.get("elevation", metrics.get("dtm_stats", {}))
        if elev:
            c1, c2, c3 = st.columns(3)
            c1.metric("Min elevation", f"{elev.get('min', 'N/A')}")
            c2.metric("Max elevation", f"{elev.get('max', 'N/A')}")
            c3.metric("Mean elevation", f"{elev.get('mean', 'N/A')}")

    with st.expander("Raw JSON"):
        st.json(metrics)


def _render_downloads(outputs: dict[str, Path | None]):
    """Render download buttons for available outputs."""
    st.subheader("📥 Downloads")
    cols = st.columns(3)
    for i, (label, path) in enumerate(
        [("DTM (GeoTIFF)", outputs["dtm"]),
         ("DSM (GeoTIFF)", outputs["dsm"]),
         ("Hillshade (GeoTIFF)", outputs["hillshade"])]
    ):
        with cols[i]:
            if path and path.exists():
                with open(path, "rb") as f:
                    st.download_button(
                        f"⬇ {label}",
                        data=f.read(),
                        file_name=path.name,
                        mime="image/tiff",
                        use_container_width=True,
                    )
            else:
                st.button(f"⬇ {label}", disabled=True, use_container_width=True)

    if outputs["qa_report"] and outputs["qa_report"].exists():
        with open(outputs["qa_report"], "rb") as f:
            st.download_button(
                "⬇ QA Report (HTML)",
                data=f.read(),
                file_name="qa_report.html",
                mime="text/html",
            )


def _render_preview(outputs: dict[str, Path | None]):
    """Show hillshade preview image if available."""
    preview = outputs.get("hillshade_preview")
    if preview and preview.exists():
        st.subheader("🗺️ Hillshade Preview")
        st.image(str(preview), use_container_width=True)


def render_results(params: PipelineParams):
    """Render the Results tab."""
    if not params.output_dir:
        st.info("Set an output directory and run the pipeline to see results here.")
        return

    output_path = Path(params.output_dir)
    if not output_path.is_dir():
        st.info("Output directory doesn't exist yet. Run the pipeline first.")
        return

    outputs = _find_outputs(params.output_dir)

    has_any = any(v and v.exists() for v in outputs.values())
    if not has_any:
        st.info("No outputs found yet. Run the pipeline to generate results.")
        return

    # ── Preview ──
    _render_preview(outputs)

    # ── QA Metrics ──
    if outputs["qa_metrics"] and outputs["qa_metrics"].exists():
        _render_qa_metrics(outputs["qa_metrics"])

    # ── Downloads ──
    _render_downloads(outputs)
