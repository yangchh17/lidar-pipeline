# Testing Guide

## Quick Start

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Test Structure

```
tests/
├── test_validators.py   # Input validation (LAS headers, CRS, disk, memory)
├── test_progress.py     # Log parser regex matching, PipelineStatus updates
├── test_runner.py       # Command builder output verification
├── test_cli.py          # Click CLI integration (CliRunner)
└── __init__.py
```

## What's Tested

### Unit Tests (32 tests, all passing)

**`test_validators.py`** — Validates pre-flight checks:
- Missing/empty input directory
- Invalid parameter ranges (resolution ≤ 0, bad rigidness)
- LAS file header reading and CRS detection
- Disk space and memory warnings

**`test_progress.py`** — Validates log parsing:
- Step detection (`Step 1:`, `Step 2:`, etc.)
- Tile progress (`3/10`, `10/10`)
- Pipeline completion (`Pipeline complete (2.5 minutes)`)
- Error/warning line capture
- `step_pct` and `overall_pct` calculations

**`test_runner.py`** — Validates command construction:
- Default parameter values in command
- Flag inclusion (`--skip-dtm`, `--resume`, `--verbose`)
- Config file argument placement

**`test_cli.py`** — Validates CLI integration:
- `--help` output
- `--version` output
- Missing required arguments
- `--dry-run` mode

## Running Tests

```bash
# All tests
pytest tests/ -v

# Single file
pytest tests/test_validators.py -v

# With coverage
pytest tests/ -v --cov=lidar_pipeline --cov-report=term-missing

# Stop on first failure
pytest tests/ -x
```

## Writing New Tests

Follow existing patterns. Tests use `tmp_path` for filesystem fixtures and `unittest.mock` for mocking laspy/subprocess.

Example:

```python
def test_my_feature(tmp_path):
    """Test description."""
    # Arrange
    input_dir = tmp_path / "tiles"
    input_dir.mkdir()

    # Act
    result = my_function(str(input_dir))

    # Assert
    assert result.ok
```

## Integration Tests (TODO)

Integration tests with real LAS data are planned. They will:
- Use a small synthetic LAS dataset (see `tests/data/`)
- Run the full R pipeline end-to-end
- Verify output rasters exist and have correct CRS/resolution
- Require R to be installed (skipped in CI if unavailable)

## CI

GitHub Actions runs `pytest tests/ -v` on every push/PR to `main`. See `.github/workflows/ci.yml`.
