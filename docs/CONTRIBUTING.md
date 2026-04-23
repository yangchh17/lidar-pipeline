# Contributing

Thanks for your interest in contributing to the LiDAR Processing Pipeline.

## Setup

```bash
git clone https://github.com/yangchh/lidar-pipeline.git
cd lidar-pipeline
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

You also need R ≥ 4.2 with the required packages:

```r
install.packages(c("lidR", "terra", "argparse", "yaml", "futile.logger", "R6", "jsonlite", "progress"))
```

## Project Structure

```
lidar_pipeline/     Python package (CLI, validators, runner, progress)
app/                Streamlit GUI
tests/              Unit tests (pytest)
docs/               Documentation
run_lidar_pipeline.R   R engine
```

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes
3. Run tests: `pytest tests/ -v`
4. Commit with a conventional message: `feat:`, `fix:`, `docs:`, `test:`, `chore:`
5. Push and open a PR against `main`

## Code Style

- Python: follow PEP 8, use type hints, docstrings for public functions
- R: use `futile.logger` for output (not `cat()`/`print()`), snake_case naming
- Keep functions focused — one responsibility per function

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=lidar_pipeline --cov-report=term-missing
```

See [TESTING.md](TESTING.md) for details on writing tests.

## Adding a New Feature

1. If it touches the R engine: update `run_lidar_pipeline.R` and add a CLI flag
2. If it touches the Python CLI: update `cli.py` and `runner.py` (command builder)
3. If it touches the GUI: add/modify the relevant `app/components/` module
4. Add tests for any new Python code
5. Update docs (README parameter table, API reference, etc.)

## Reporting Issues

Open a GitHub issue with:
- What you expected vs what happened
- Steps to reproduce
- OS, Python version, R version
- Relevant log output
