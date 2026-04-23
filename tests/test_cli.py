"""Tests for lidar_pipeline.cli (Click integration)."""

import struct
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from lidar_pipeline.cli import main


def _write_minimal_las(path: Path, point_count: int = 100) -> None:
    header_size = 227
    point_size = 20
    header = bytearray(header_size)
    header[0:4] = b"LASF"
    header[24] = 1
    header[25] = 2
    struct.pack_into("<H", header, 94, header_size)
    struct.pack_into("<I", header, 96, header_size)
    struct.pack_into("<I", header, 100, 0)
    header[104] = 0
    struct.pack_into("<H", header, 105, point_size)
    struct.pack_into("<I", header, 107, point_count)
    with open(path, "wb") as f:
        f.write(header)
        f.write(b"\x00" * point_size * point_count)


@pytest.fixture()
def las_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tiles"
    d.mkdir()
    _write_minimal_las(d / "tile.las", 200)
    return d


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "LiDAR terrain processing pipeline" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.2.0" in result.output

    def test_dry_run(self, las_dir, tmp_path):
        output = tmp_path / "out"
        runner = CliRunner()
        result = runner.invoke(main, [
            "--input", str(las_dir),
            "--output", str(output),
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.output
        assert "1 tiles" in result.output

    def test_validation_failure_bad_resolution(self, las_dir, tmp_path):
        output = tmp_path / "out"
        runner = CliRunner()
        result = runner.invoke(main, [
            "--input", str(las_dir),
            "--output", str(output),
            "--resolution", "0",
        ])
        assert result.exit_code != 0
        assert "Resolution" in result.output

    def test_missing_input_dir(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, [
            "--input", str(tmp_path / "nope"),
            "--output", str(tmp_path / "out"),
        ])
        # Click catches the bad path before we even get to validation
        assert result.exit_code != 0
