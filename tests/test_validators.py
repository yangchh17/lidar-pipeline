"""Tests for lidar_pipeline.validators."""

import struct
import tempfile
from pathlib import Path

import pytest

from lidar_pipeline.validators import ValidationResult, validate_inputs


# ---------------------------------------------------------------------------
# Helpers — create minimal valid LAS 1.2 files
# ---------------------------------------------------------------------------

def _write_minimal_las(path: Path, point_count: int = 100) -> None:
    """Write a bare-bones LAS 1.2 file with no VLRs and *point_count* points."""
    # LAS 1.2, point format 0 (20 bytes per point), no VLRs
    header_size = 227
    point_size = 20
    data_offset = header_size
    file_sig = b"LASF"
    version_major = 1
    version_minor = 2
    point_format = 0
    num_vlrs = 0

    header = bytearray(header_size)
    header[0:4] = file_sig
    header[24] = version_major
    header[25] = version_minor
    struct.pack_into("<H", header, 94, header_size)       # header size
    struct.pack_into("<I", header, 96, data_offset)       # offset to point data
    struct.pack_into("<I", header, 100, num_vlrs)         # number of VLRs
    header[104] = point_format                            # point data format
    struct.pack_into("<H", header, 105, point_size)       # point record length
    struct.pack_into("<I", header, 107, point_count)      # legacy number of points

    with open(path, "wb") as f:
        f.write(header)
        f.write(b"\x00" * point_size * point_count)


@pytest.fixture()
def las_dir(tmp_path: Path) -> Path:
    """Create a temp directory with two minimal LAS files."""
    d = tmp_path / "tiles"
    d.mkdir()
    _write_minimal_las(d / "tile_a.las", 500)
    _write_minimal_las(d / "tile_b.las", 300)
    return d


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "output"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_defaults(self):
        r = ValidationResult()
        assert r.ok is True
        assert r.errors == []
        assert r.warnings == []

    def test_add_error_flips_ok(self):
        r = ValidationResult()
        r.add_error("boom")
        assert r.ok is False
        assert "boom" in r.errors

    def test_add_warning_keeps_ok(self):
        r = ValidationResult()
        r.add_warning("hmm")
        assert r.ok is True
        assert "hmm" in r.warnings


class TestValidateInputs:
    def test_missing_input_dir(self, tmp_path, output_dir):
        r = validate_inputs(
            tmp_path / "nope", output_dir, resolution=0.5, cores=1, csf_rigidness=3
        )
        assert r.ok is False
        assert any("does not exist" in e for e in r.errors)

    def test_empty_input_dir(self, tmp_path, output_dir):
        empty = tmp_path / "empty"
        empty.mkdir()
        r = validate_inputs(empty, output_dir, resolution=0.5, cores=1, csf_rigidness=3)
        assert r.ok is False
        assert any("No LAS/LAZ" in e for e in r.errors)

    def test_bad_resolution(self, las_dir, output_dir):
        r = validate_inputs(las_dir, output_dir, resolution=-1, cores=1, csf_rigidness=3)
        assert r.ok is False
        assert any("Resolution" in e for e in r.errors)

    def test_bad_cores(self, las_dir, output_dir):
        r = validate_inputs(las_dir, output_dir, resolution=0.5, cores=0, csf_rigidness=3)
        assert r.ok is False
        assert any("Cores" in e for e in r.errors)

    def test_bad_csf_rigidness(self, las_dir, output_dir):
        r = validate_inputs(las_dir, output_dir, resolution=0.5, cores=1, csf_rigidness=5)
        assert r.ok is False
        assert any("rigidness" in e for e in r.errors)

    def test_valid_inputs(self, las_dir, output_dir):
        r = validate_inputs(las_dir, output_dir, resolution=0.5, cores=1, csf_rigidness=3)
        assert r.ok is True
        assert r.file_count == 2
        assert r.total_points > 0
        assert r.total_size_mb > 0
