"""Results tab — visualization and downloads."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components.sidebar import PipelineParams

try:
    import rasterio
    from rasterio.warp import transform_bounds

    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

try:
    import folium
    from streamlit_folium import st_folium

    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False


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


# ── QA Metrics ──────────────────────────────────────────────────────────────

def _render_qa_metrics(metrics_path: Path):
    """Display QA metrics from the JSON report."""
    with open(metrics_path) as f:
        metrics = json.load(f)

    st.subheader("📈 QA Metrics")

    if isinstance(metrics, dict):
        if "processing_time_minutes" in metrics:
            st.metric("Processing time", f"{metrics['processing_time_minutes']:.1f} min")

        tiles = metrics.get("tiles", metrics.get("tile_metrics", []))
        if tiles and isinstance(tiles, list):
            col1, col2 = st.columns(2)
            col1.metric("Tiles processed", len(tiles))
            total_pts = sum(t.get("point_count", t.get("raw_points", 0)) for t in tiles)
            col2.metric("Total points", f"{total_pts:,}")

        elev = metrics.get("elevation", metrics.get("dtm_stats", {}))
        if elev:
            c1, c2, c3 = st.columns(3)
            c1.metric("Min elevation", f"{elev.get('min', 'N/A')}")
            c2.metric("Max elevation", f"{elev.get('max', 'N/A')}")
            c3.metric("Mean elevation", f"{elev.get('mean', 'N/A')}")

    with st.expander("Raw JSON"):
        st.json(metrics)


# ── Raster Stats ────────────────────────────────────────────────────────────

def _raster_stats(tif_path: Path) -> dict | None:
    """Read basic stats from a single-band GeoTIFF."""
    if not HAS_RASTERIO or not tif_path.exists():
        return None
    try:
        with rasterio.open(tif_path) as src:
            data = src.read(1)
            nodata = src.nodata
            if nodata is not None:
                mask = data != nodata
            else:
                mask = np.isfinite(data)
            valid = data[mask]
            if valid.size == 0:
                return None
            return {
                "min": float(np.min(valid)),
                "max": float(np.max(valid)),
                "mean": float(np.mean(valid)),
                "std": float(np.std(valid)),
                "valid_pct": float(mask.sum() / data.size * 100),
                "shape": data.shape,
                "crs": str(src.crs) if src.crs else "Unknown",
                "resolution": src.res,
            }
    except Exception:
        return None


def _render_raster_stats(outputs: dict[str, Path | None]):
    """Show elevation statistics for DTM and DSM."""
    st.subheader("📊 Raster Statistics")

    cols = st.columns(2)
    for col, (label, key) in zip(cols, [("DTM", "dtm"), ("DSM", "dsm")]):
        path = outputs.get(key)
        if path and path.exists():
            stats = _raster_stats(path)
            if stats:
                with col:
                    st.markdown(f"**{label}**")
                    st.metric("Min", f"{stats['min']:.2f} m")
                    st.metric("Max", f"{stats['max']:.2f} m")
                    st.metric("Mean", f"{stats['mean']:.2f} m")
                    st.metric("Std Dev", f"{stats['std']:.2f} m")
                    st.caption(
                        f"{stats['shape'][1]}×{stats['shape'][0]} px · "
                        f"{stats['resolution'][0]:.2f} m · "
                        f"{stats['valid_pct']:.1f}% valid · "
                        f"CRS: {stats['crs']}"
                    )


# ── Folium Geographic Map ────────────────────────────────────────────────────

def _render_geographic_map(outputs: dict[str, Path | None]):
    """Render an interactive folium map with DTM/hillshade overlay on a basemap."""
    if not HAS_FOLIUM or not HAS_RASTERIO:
        return

    # Prefer hillshade for visual overlay, fall back to DTM
    overlay_path = outputs.get("hillshade") or outputs.get("dtm")
    if not overlay_path or not overlay_path.exists():
        return

    st.subheader("🌍 Geographic Map")

    try:
        with rasterio.open(overlay_path) as src:
            data = src.read(1)
            bounds = src.bounds
            src_crs = src.crs
            nodata = src.nodata

        # Reproject bounds to EPSG:4326 for folium
        if src_crs and str(src_crs) != "EPSG:4326":
            try:
                west, south, east, north = transform_bounds(
                    src_crs, "EPSG:4326",
                    bounds.left, bounds.bottom, bounds.right, bounds.top,
                )
            except Exception:
                west, south, east, north = bounds.left, bounds.bottom, bounds.right, bounds.top
        else:
            west, south, east, north = bounds.left, bounds.bottom, bounds.right, bounds.top

        center_lat = (south + north) / 2
        center_lon = (west + east) / 2

        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

        # Normalize raster to 0-255 grayscale PNG for overlay
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)
        vmin = np.nanmin(data)
        vmax = np.nanmax(data)
        if vmax > vmin:
            normalized = (data - vmin) / (vmax - vmin) * 255
        else:
            normalized = np.zeros_like(data)
        normalized = np.nan_to_num(normalized, nan=0).astype(np.uint8)

        # Create RGBA image (grayscale with transparency for nodata)
        from io import BytesIO
        from PIL import Image

        rgba = np.zeros((*normalized.shape, 4), dtype=np.uint8)
        rgba[..., 0] = normalized
        rgba[..., 1] = normalized
        rgba[..., 2] = normalized
        if nodata is not None:
            rgba[..., 3] = np.where(np.isnan(data), 0, 200).astype(np.uint8)
        else:
            rgba[..., 3] = 200

        # Downsample if large
        max_dim = 1024
        h, w = rgba.shape[:2]
        if max(h, w) > max_dim:
            img = Image.fromarray(rgba)
            factor = max_dim / max(h, w)
            img = img.resize((int(w * factor), int(h * factor)), Image.LANCZOS)
            rgba = np.array(img)

        # Encode as PNG in memory
        img = Image.fromarray(rgba)
        buf = BytesIO()
        img.save(buf, format="PNG")
        import base64
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        img_url = f"data:image/png;base64,{img_b64}"

        folium.raster_layers.ImageOverlay(
            image=img_url,
            bounds=[[south, west], [north, east]],
            opacity=0.7,
            name="Terrain",
        ).add_to(m)

        folium.LayerControl().add_to(m)

        st_folium(m, width=None, height=450, use_container_width=True)

    except Exception as exc:
        st.warning(f"Could not render geographic map: {exc}")


# ── Hillshade Heatmap ───────────────────────────────────────────────────────

def _render_elevation_heatmap(outputs: dict[str, Path | None]):
    """Render an interactive plotly heatmap of the DTM."""
    dtm_path = outputs.get("dtm")
    if not dtm_path or not dtm_path.exists() or not HAS_RASTERIO:
        return

    st.subheader("🗺️ Elevation Heatmap")

    try:
        with rasterio.open(dtm_path) as src:
            data = src.read(1)
            nodata = src.nodata

        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)

        # Downsample large rasters for browser performance
        max_dim = 800
        h, w = data.shape
        if max(h, w) > max_dim:
            factor = max(h, w) / max_dim
            new_h, new_w = int(h / factor), int(w / factor)
            # Simple block-mean downsample
            data = data[:new_h * int(factor), :new_w * int(factor)]
            data = data.reshape(new_h, int(factor), new_w, int(factor))
            with np.errstate(all="ignore"):
                data = np.nanmean(data, axis=(1, 3))

        fig = px.imshow(
            data,
            color_continuous_scale="terrain",
            labels={"color": "Elevation (m)"},
            aspect="equal",
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            height=500,
            coloraxis_colorbar=dict(title="m"),
        )
        st.plotly_chart(fig, use_container_width=True)

    except Exception as exc:
        st.warning(f"Could not render elevation heatmap: {exc}")


# ── Elevation Profile ───────────────────────────────────────────────────────

def _render_elevation_profile(outputs: dict[str, Path | None]):
    """Draw an elevation profile across the center row of the DTM."""
    dtm_path = outputs.get("dtm")
    if not dtm_path or not dtm_path.exists() or not HAS_RASTERIO:
        return

    st.subheader("📐 Elevation Profile (center transect)")

    try:
        with rasterio.open(dtm_path) as src:
            data = src.read(1)
            nodata = src.nodata
            res_x = src.res[0]

        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)

        mid_row = data.shape[0] // 2
        profile = data[mid_row, :]
        distance = np.arange(len(profile)) * res_x

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=distance,
            y=profile,
            mode="lines",
            line=dict(color="#2E86AB", width=1.5),
            name="Elevation",
        ))
        fig.update_layout(
            xaxis_title="Distance (m)",
            yaxis_title="Elevation (m)",
            margin=dict(l=0, r=0, t=30, b=0),
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    except Exception as exc:
        st.warning(f"Could not render elevation profile: {exc}")


# ── Downloads ───────────────────────────────────────────────────────────────

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


# ── Preview ─────────────────────────────────────────────────────────────────

def _render_preview(outputs: dict[str, Path | None]):
    """Show hillshade preview image if available."""
    preview = outputs.get("hillshade_preview")
    if preview and preview.exists():
        st.subheader("🏔️ Hillshade Preview")
        st.image(str(preview), use_container_width=True)


# ── Main entry ──────────────────────────────────────────────────────────────

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

    # ── Geographic map (folium) ──
    if HAS_FOLIUM and HAS_RASTERIO:
        _render_geographic_map(outputs)

    # ── Hillshade preview ──
    _render_preview(outputs)

    # ── Interactive elevation heatmap ──
    _render_elevation_heatmap(outputs)

    # ── Elevation profile ──
    _render_elevation_profile(outputs)

    # ── Raster stats ──
    if HAS_RASTERIO:
        _render_raster_stats(outputs)

    # ── QA Metrics from JSON ──
    if outputs["qa_metrics"] and outputs["qa_metrics"].exists():
        _render_qa_metrics(outputs["qa_metrics"])

    # ── Downloads ──
    _render_downloads(outputs)
