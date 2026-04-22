"""Input validation for LAS/LAZ datasets before pipeline execution."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import laspy
import psutil


@dataclass
class ValidationResult:
    """Aggregated validation outcome."""

    ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    file_count: int = 0
    total_points: int = 0
    total_size_mb: float = 0.0
    crs_epsg: Optional[int] = None

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_inputs(
    input_dir: str | Path,
    output_dir: str | Path,
    resolution: float,
    cores: int,
    csf_rigidness: int,
) -> ValidationResult:
    """Run all pre-flight checks and return a ValidationResult."""
    result = ValidationResult()
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # --- Input directory ---
    if not input_path.is_dir():
        result.add_error(f"Input directory does not exist: {input_path}")
        return result

    las_files = sorted(
        p for p in input_path.iterdir()
        if p.suffix.lower() in (".las", ".laz")
    )

    if not las_files:
        result.add_error(f"No LAS/LAZ files found in: {input_path}")
        return result

    result.file_count = len(las_files)
    result.total_size_mb = sum(f.stat().st_size for f in las_files) / (1024 ** 2)

    # --- Parameter ranges ---
    if resolution <= 0:
        result.add_error(f"Resolution must be positive, got {resolution}")
    if cores < 1:
        result.add_error(f"Cores must be >= 1, got {cores}")
    if csf_rigidness not in (1, 2, 3):
        result.add_error(f"CSF rigidness must be 1, 2, or 3, got {csf_rigidness}")

    # --- LAS file validation ---
    crs_set: set[str] = set()
    for las_file in las_files:
        try:
            with laspy.open(las_file) as reader:
                header = reader.header
                result.total_points += header.point_count

                # Collect CRS from VLRs (WKT or GeoTIFF keys)
                for vlr in header.vlrs:
                    if vlr.record_id in (2111, 2112, 34735):
                        crs_set.add(vlr.record_data[:80].decode("ascii", errors="ignore"))
        except Exception as exc:
            result.add_error(f"Cannot read {las_file.name}: {exc}")

    if len(crs_set) > 1:
        result.add_warning(
            f"Multiple CRS detected across tiles ({len(crs_set)} variants). "
            "Consider reprojecting to a single CRS before processing."
        )

    # --- Disk space ---
    try:
        disk = shutil.disk_usage(output_path.parent if output_path.exists() else output_path.anchor)
        estimated_output_mb = result.total_size_mb * 3  # rough multiplier
        free_mb = disk.free / (1024 ** 2)
        if free_mb < estimated_output_mb:
            result.add_warning(
                f"Low disk space: ~{free_mb:.0f} MB free, estimated need ~{estimated_output_mb:.0f} MB"
            )
    except OSError:
        pass

    # --- Memory estimate ---
    mem = psutil.virtual_memory()
    available_gb = mem.available / (1024 ** 3)
    if result.total_size_mb > available_gb * 1024 * 0.5:
        result.add_warning(
            f"Dataset ({result.total_size_mb:.0f} MB) may exceed available RAM "
            f"({available_gb:.1f} GB). Consider reducing chunk size or cores."
        )

    return result
