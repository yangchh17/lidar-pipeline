"""Tests for lidar_pipeline.progress."""

import pytest

from lidar_pipeline.progress import LogParser, PipelineStatus, STEP_LABELS


class TestPipelineStatus:
    def test_defaults(self):
        s = PipelineStatus()
        assert s.current_step == 0
        assert s.overall_pct == 0.0

    def test_step_pct(self):
        s = PipelineStatus(tiles_done=5, tiles_total=10)
        assert s.step_pct == 50.0

    def test_step_pct_zero_total(self):
        s = PipelineStatus(tiles_done=0, tiles_total=0)
        assert s.step_pct == 0.0

    def test_overall_pct_midway(self):
        s = PipelineStatus(current_step=3, total_steps=5, tiles_done=5, tiles_total=10)
        # completed steps = 2, step_frac = 0.5 → (2 + 0.5) / 5 = 50%
        assert s.overall_pct == pytest.approx(50.0)


class TestLogParser:
    def test_step_detection(self):
        parser = LogParser()
        parser.feed("INFO [2026-04-22 10:00:00] Step 2: Ground classification")
        assert parser.status.current_step == 2
        assert parser.status.step_label == STEP_LABELS[2]

    def test_tile_progress(self):
        parser = LogParser()
        parser.feed("INFO Processing tile 3/10")
        assert parser.status.tiles_done == 3
        assert parser.status.tiles_total == 10

    def test_pipeline_done(self):
        parser = LogParser()
        parser.feed("INFO Pipeline complete (12.5 minutes)")
        assert parser.status.finished is True
        assert parser.status.elapsed_minutes == pytest.approx(12.5)

    def test_error_capture(self):
        parser = LogParser()
        parser.feed("ERROR Failed to read tile_x.las")
        assert len(parser.status.errors) == 1

    def test_warning_capture(self):
        parser = LogParser()
        parser.feed("WARN CRS mismatch detected")
        assert len(parser.status.warnings) == 1

    def test_callback_fires(self):
        updates = []
        parser = LogParser(on_update=lambda s: updates.append(s.current_step))
        parser.feed("Step 1: Filtering")
        parser.feed("Step 2: Classification")
        assert updates == [1, 2]

    def test_step_resets_tile_counts(self):
        parser = LogParser()
        parser.feed("Step 1: Filtering")
        parser.feed("Processing tile 5/10")
        assert parser.status.tiles_done == 5
        parser.feed("Step 2: Classification")
        assert parser.status.tiles_done == 0
        assert parser.status.tiles_total == 0

    def test_blank_lines_ignored(self):
        parser = LogParser()
        parser.feed("")
        parser.feed("   ")
        assert parser.status.current_step == 0
