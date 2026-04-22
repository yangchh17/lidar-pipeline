"""CLI entry point for the LiDAR processing pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from tqdm import tqdm

from . import __version__
from .progress import PipelineStatus
from .runner import run_pipeline
from .validators import validate_inputs


class _ProgressBar:
    """Thin wrapper around tqdm that updates from PipelineStatus callbacks."""

    def __init__(self):
        self._bar: tqdm | None = None
        self._last_step = 0

    def update(self, status: PipelineStatus) -> None:
        if status.current_step != self._last_step:
            if self._bar is not None:
                self._bar.close()
            desc = f"[{status.current_step}/{status.total_steps}] {status.step_label}"
            total = status.tiles_total or None
            self._bar = tqdm(total=total, desc=desc, unit="tile", leave=True)
            self._last_step = status.current_step

        if self._bar is not None and status.tiles_total:
            increment = status.tiles_done - (self._bar.n or 0)
            if increment > 0:
                self._bar.update(increment)

        if status.finished and self._bar is not None:
            self._bar.close()

    def close(self):
        if self._bar is not None:
            self._bar.close()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="lidar-pipeline")
@click.option("--input", "-i", "input_dir", required=True, type=click.Path(exists=True, file_okay=False), help="Directory containing LAS/LAZ tiles.")
@click.option("--output", "-o", "output_dir", required=True, type=click.Path(file_okay=False), help="Output directory for results.")
@click.option("--config", "-c", type=click.Path(exists=True, dir_okay=False), help="YAML config file (CLI args override).")
@click.option("--resolution", type=float, default=0.5, show_default=True, help="Raster resolution in metres.")
@click.option("--csf-cloth-res", type=float, default=0.6, show_default=True, help="CSF cloth resolution.")
@click.option("--csf-threshold", type=float, default=0.4, show_default=True, help="CSF classification threshold.")
@click.option("--csf-rigidness", type=click.IntRange(1, 3), default=3, show_default=True, help="1=flat, 2=moderate, 3=steep.")
@click.option("--chunk-size", type=int, default=250, show_default=True, help="Processing chunk size (metres).")
@click.option("--chunk-buffer", type=int, default=50, show_default=True, help="Chunk buffer (metres).")
@click.option("--cores", type=int, default=1, show_default=True, help="Parallel processing cores.")
@click.option("--hillshade-angle", type=float, default=40.0, show_default=True, help="Sun elevation for hillshade.")
@click.option("--hillshade-direction", type=float, default=270.0, show_default=True, help="Sun azimuth for hillshade.")
@click.option("--skip-dtm", is_flag=True, help="Skip DTM generation.")
@click.option("--skip-dsm", is_flag=True, help="Skip DSM generation.")
@click.option("--skip-hillshade", is_flag=True, help="Skip hillshade generation.")
@click.option("--resume", is_flag=True, help="Resume from checkpoint.")
@click.option("--dry-run", is_flag=True, help="Validate inputs only, no processing.")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug-level output.")
@click.option("--no-progress", is_flag=True, help="Disable progress bars.")
def main(
    input_dir: str,
    output_dir: str,
    config: str | None,
    resolution: float,
    csf_cloth_res: float,
    csf_threshold: float,
    csf_rigidness: int,
    chunk_size: int,
    chunk_buffer: int,
    cores: int,
    hillshade_angle: float,
    hillshade_direction: float,
    skip_dtm: bool,
    skip_dsm: bool,
    skip_hillshade: bool,
    resume: bool,
    dry_run: bool,
    verbose: bool,
    no_progress: bool,
) -> None:
    """LiDAR terrain processing pipeline.

    Wraps the R engine (lidR) with Python-side input validation,
    progress tracking, and a friendlier CLI.
    """
    # ── Pre-flight validation ──
    click.echo("Validating inputs...")
    result = validate_inputs(
        input_dir=input_dir,
        output_dir=output_dir,
        resolution=resolution,
        cores=cores,
        csf_rigidness=csf_rigidness,
    )

    for w in result.warnings:
        click.secho(f"  ⚠ {w}", fg="yellow")

    if not result.ok:
        for e in result.errors:
            click.secho(f"  ✗ {e}", fg="red")
        raise SystemExit(1)

    click.echo(
        f"  ✓ {result.file_count} tiles, "
        f"{result.total_points:,} points, "
        f"{result.total_size_mb:.1f} MB"
    )

    if dry_run:
        click.echo("Dry run — stopping before processing.")
        return

    # ── Ensure output dir exists ──
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ── Progress callback ──
    progress = None if no_progress else _ProgressBar()
    on_progress = progress.update if progress else None

    # ── Run R engine ──
    click.echo()
    outcome = run_pipeline(
        input_dir=input_dir,
        output_dir=output_dir,
        on_progress=on_progress,
        config=config,
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
        dry_run=dry_run,
        verbose=verbose,
    )

    if progress:
        progress.close()

    # ── Summary ──
    click.echo()
    if outcome["success"]:
        click.secho(
            f"✓ Pipeline complete ({outcome['elapsed_minutes']:.1f} min)",
            fg="green",
            bold=True,
        )
    else:
        click.secho(
            f"✗ Pipeline failed (exit code {outcome['exit_code']})",
            fg="red",
            bold=True,
        )
        for err in outcome["errors"]:
            click.secho(f"  {err}", fg="red")
        raise SystemExit(outcome["exit_code"])

    if outcome["warnings"]:
        click.secho(f"  {len(outcome['warnings'])} warning(s) during processing", fg="yellow")


if __name__ == "__main__":
    main()
