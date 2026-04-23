"""Tests for lidar_pipeline.runner (command building only — no R required)."""

from unittest.mock import patch

import pytest

from lidar_pipeline.runner import build_command


@pytest.fixture(autouse=True)
def _mock_rscript():
    """Stub out Rscript/R-script-path lookups so tests don't need R installed."""
    with (
        patch("lidar_pipeline.runner._find_rscript", return_value="Rscript"),
        patch(
            "lidar_pipeline.runner._r_script_path",
            return_value="run_lidar_pipeline.R",
        ),
    ):
        yield


class TestBuildCommand:
    def test_minimal(self):
        cmd = build_command("in", "out")
        assert cmd[:2] == ["Rscript", "run_lidar_pipeline.R"]
        assert "--input" in cmd
        assert "--output" in cmd

    def test_config_flag(self):
        cmd = build_command("in", "out", config="my.yaml")
        idx = cmd.index("--config")
        assert cmd[idx + 1] == "my.yaml"

    def test_skip_flags(self):
        cmd = build_command("in", "out", skip_dtm=True, skip_dsm=True, skip_hillshade=True)
        assert "--skip-dtm" in cmd
        assert "--skip-dsm" in cmd
        assert "--skip-hillshade" in cmd

    def test_resume_and_dry_run(self):
        cmd = build_command("in", "out", resume=True, dry_run=True, verbose=True)
        assert "--resume" in cmd
        assert "--dry-run" in cmd
        assert "--verbose" in cmd

    def test_numeric_params(self):
        cmd = build_command(
            "in", "out",
            resolution=1.0,
            csf_rigidness=2,
            cores=4,
            chunk_size=500,
        )
        idx = cmd.index("--resolution")
        assert cmd[idx + 1] == "1.0"
        idx = cmd.index("--csf-rigidness")
        assert cmd[idx + 1] == "2"
        idx = cmd.index("--cores")
        assert cmd[idx + 1] == "4"
        idx = cmd.index("--chunk-size")
        assert cmd[idx + 1] == "500"

    def test_no_skip_flags_when_false(self):
        cmd = build_command("in", "out")
        assert "--skip-dtm" not in cmd
        assert "--skip-dsm" not in cmd
        assert "--skip-hillshade" not in cmd
        assert "--resume" not in cmd
        assert "--dry-run" not in cmd
