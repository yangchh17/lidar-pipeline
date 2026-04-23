# API Reference

## Python Package: `lidar_pipeline`

### `lidar_pipeline.validators`

#### `ValidationResult`

Dataclass holding pre-flight check results.

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | `True` if no errors found |
| `errors` | `list[str]` | Blocking issues |
| `warnings` | `list[str]` | Non-blocking advisories |
| `file_count` | `int` | Number of LAS/LAZ files found |
| `total_points` | `int` | Sum of point counts across all files |
| `total_size_mb` | `float` | Total input size in MB |
| `crs_epsg` | `int \| None` | Detected EPSG code (if uniform) |

Methods:
- `add_error(msg: str)` — Append error and set `ok = False`
- `add_warning(msg: str)` — Append warning

#### `validate_inputs(input_dir, output_dir, resolution, cores, csf_rigidness) → ValidationResult`

Runs all pre-flight checks:
1. Input directory exists and contains LAS/LAZ files
2. Parameter ranges are valid
3. LAS headers are readable (via laspy)
4. CRS consistency across tiles
5. Disk space estimate for outputs
6. Available RAM vs dataset size

---

### `lidar_pipeline.runner`

#### `build_command(input_dir, output_dir, **kwargs) → list[str]`

Constructs the full `Rscript run_lidar_pipeline.R ...` command as a list of strings. Accepts all pipeline parameters as keyword arguments.

#### `run_pipeline(input_dir, output_dir, on_progress=None, **kwargs) → dict`

Executes the R engine as a subprocess with real-time log streaming.

**Parameters:**
- `input_dir` — Path to LAS/LAZ tile directory
- `output_dir` — Path for output rasters
- `on_progress` — Optional callback `(PipelineStatus) → None`, called on each log line
- `**kwargs` — All pipeline parameters (resolution, cores, csf_*, etc.)

**Returns:**
```python
{
    "success": bool,
    "exit_code": int,
    "elapsed_minutes": float,
    "errors": list[str],
    "warnings": list[str],
}
```

---

### `lidar_pipeline.progress`

#### `PipelineStatus`

Dataclass representing a snapshot of pipeline progress.

| Field | Type | Description |
|-------|------|-------------|
| `current_step` | `int` | Current processing step (1-5) |
| `total_steps` | `int` | Always 5 |
| `step_label` | `str` | Human-readable step name |
| `tiles_done` | `int` | Tiles completed in current step |
| `tiles_total` | `int` | Total tiles in current step |
| `finished` | `bool` | Pipeline completed |
| `elapsed_minutes` | `float` | Total runtime |
| `errors` | `list[str]` | Error lines from R log |
| `warnings` | `list[str]` | Warning lines from R log |

Properties:
- `step_pct → float` — Current step progress (0-100)
- `overall_pct → float` — Overall pipeline progress (0-100)

#### `LogParser`

Stateful parser that feeds R log lines into a `PipelineStatus`.

```python
parser = LogParser(on_update=my_callback)
parser.feed("INFO Step 2: Ground classification")
parser.feed("INFO Processing tile 3/10")
print(parser.status.overall_pct)  # ~26.0
```

---

### `lidar_pipeline.cli`

Entry point: `lidar-pipeline` (installed via `pip install -e .`)

```bash
lidar-pipeline --help
lidar-pipeline --input ./tiles --output ./results
lidar-pipeline --input ./tiles --output ./results --resolution 1.0 --cores 4 --dry-run
```

See `README.md` for the full parameter table.

---

## Streamlit GUI

### `app.components.sidebar`

#### `PipelineParams`

Dataclass mirroring all CLI parameters plus computed properties:
- `input_valid → bool` — Input directory exists
- `has_las_files → bool` — Directory contains LAS/LAZ files

#### `render_sidebar() → PipelineParams`

Renders the Streamlit sidebar and returns current parameter values.

### `app.components.runner`

#### `render_runner(params: PipelineParams)`

Renders the Run tab: validation summary, run/dry-run buttons, progress display, error suggestions.

### `app.components.results`

#### `render_results(params: PipelineParams)`

Renders the Results tab: folium geographic map, plotly elevation heatmap, elevation profile, raster statistics, QA metrics, download buttons.

### `app.components.batch`

#### `Job` / `JobStatus`

Job dataclass with status enum (`PENDING`, `RUNNING`, `COMPLETE`, `FAILED`).

#### `render_batch_panel(params_dict: dict)`

Renders the Batch tab: job queue display, add/run/clear controls.
