"""Subprocess wrapper for the R LiDAR pipeline engine."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from .progress import LogParser, PipelineStatus


def _find_rscript() -> str:
    """Locate the Rscript executable."""
    rscript = shutil.which("Rscript")
    if rscript is None:
        raise FileNotFoundError(
            "Rscript not found on PATH. Install R (https://cran.r-project.org/) "
            "and ensure Rscript is accessible."
        )
    return rscript


def _r_script_path() -> Path:
    """Return the path to run_lidar_pipeline.R shipped alongside this package."""
    # The R script lives in the repo root, one level above the Python package
    candidate = Path(__file__).resolve().parent.parent / "run_lidar_pipeline.R"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"R pipeline script not found at {candidate}")


def build_command(
    input_dir: str,
    output_dir: str,
    *,
    config: Optional[str] = None,
    resolution: float = 0.5,
    csf_cloth_res: float = 0.6,
    csf_threshold: float = 0.4,
    csf_rigidness: int = 3,
    chunk_size: int = 250,
    chunk_buffer: int = 50,
    cores: int = 1,
    hillshade_angle: float = 40.0,
    hillshade_direction: float = 270.0,
    skip_dtm: bool = False,
    skip_dsm: bool = False,
    skip_hillshade: bool = False,
    resume: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[str]:
    """Build the Rscript command-line invocation."""
    cmd = [_find_rscript(), str(_r_script_path())]

    if config:
        cmd += ["--config", config]

    cmd += ["--input", input_dir, "--output", output_dir]
    cmd += ["--resolution", str(resolution)]
    cmd += ["--csf-cloth-res", str(csf_cloth_res)]
    cmd += ["--csf-threshold", str(csf_threshold)]
    cmd += ["--csf-rigidness", str(csf_rigidness)]
    cmd += ["--chunk-size", str(chunk_size)]
    cmd += ["--chunk-buffer", str(chunk_buffer)]
    cmd += ["--cores", str(cores)]
    cmd += ["--hillshade-angle", str(hillshade_angle)]
    cmd += ["--hillshade-direction", str(hillshade_direction)]

    if skip_dtm:
        cmd.append("--skip-dtm")
    if skip_dsm:
        cmd.append("--skip-dsm")
    if skip_hillshade:
        cmd.append("--skip-hillshade")
    if resume:
        cmd.append("--resume")
    if dry_run:
        cmd.append("--dry-run")
    if verbose:
        cmd.append("--verbose")

    return cmd


def run_pipeline(
    input_dir: str,
    output_dir: str,
    on_progress: Optional[callable] = None,
    **kwargs,
) -> dict:
    """
    Execute the R pipeline as a subprocess with real-time progress tracking.

    Returns a dict with keys: success, exit_code, elapsed_minutes, errors.
    """
    cmd = build_command(input_dir, output_dir, **kwargs)
    parser = LogParser(on_update=on_progress)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # Stream output line-by-line
    for line in proc.stdout:
        parser.feed(line)
        # Also echo to console so the user sees raw R output
        sys.stdout.write(line)
        sys.stdout.flush()

    proc.wait()

    return {
        "success": proc.returncode == 0,
        "exit_code": proc.returncode,
        "elapsed_minutes": parser.status.elapsed_minutes,
        "errors": parser.status.errors,
        "warnings": parser.status.warnings,
    }
