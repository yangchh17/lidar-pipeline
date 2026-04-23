# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Interfaces                       │
│                                                         │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  R CLI   │   │  Python CLI  │   │  Streamlit GUI │  │
│  │ (direct) │   │   (Click)    │   │   (web app)    │  │
│  └────┬─────┘   └──────┬───────┘   └───────┬────────┘  │
│       │                │                    │           │
└───────┼────────────────┼────────────────────┼───────────┘
        │                │                    │
        │         ┌──────▼───────┐    ┌───────▼────────┐
        │         │  validators  │    │   sidebar.py   │
        │         │  (pre-flight)│    │   runner.py    │
        │         └──────┬───────┘    │   results.py   │
        │                │            │   batch.py     │
        │         ┌──────▼───────┐    └───────┬────────┘
        │         │  runner.py   │◄───────────┘
        │         │ (subprocess) │
        │         └──────┬───────┘
        │                │
        │         ┌──────▼───────┐
        │         │ progress.py  │
        │         │ (log parser) │
        │         └──────┬───────┘
        │                │
┌───────▼────────────────▼────────────────────────────────┐
│                    R Engine                               │
│                                                          │
│  run_lidar_pipeline.R                                    │
│  ├── argparse CLI                                        │
│  ├── YAML config loader                                  │
│  ├── futile.logger (structured logging)                  │
│  ├── StateTracker R6 class (checkpoint/resume)           │
│  │                                                       │
│  ├── Step 1: Filter duplicates                           │
│  ├── Step 2: CSF ground classification → DTM (knnidw)    │
│  ├── Step 3: DSM generation (pitfree)                    │
│  ├── Step 4: Hillshade rendering                         │
│  └── Step 5: QA report (metrics + HTML)                  │
│                                                          │
│  Dependencies: lidR, terra, R6, jsonlite                  │
└──────────────────────────────────────────────────────────┘
```

## Component Details

### R Engine (`run_lidar_pipeline.R`)

The core processing engine. Handles all LiDAR operations via the `lidR` package:

- **Input**: Directory of LAS/LAZ tiles
- **Processing**: Dedup → CSF classification → DTM → DSM → Hillshade → QA
- **Output**: GeoTIFF rasters, QA report (HTML + JSON), processing log
- **State**: JSON checkpoint file for resume capability

### Python Package (`lidar_pipeline/`)

| Module | Purpose |
|--------|---------|
| `cli.py` | Click-based CLI that mirrors all R engine parameters |
| `validators.py` | Pre-flight checks: LAS headers (laspy), CRS consistency, disk/memory |
| `runner.py` | Builds Rscript command, runs subprocess, streams stdout |
| `progress.py` | Stateful regex parser for R log output → `PipelineStatus` |

### Streamlit GUI (`app/`)

| Module | Purpose |
|--------|---------|
| `main.py` | App entry, page config, tab layout |
| `components/sidebar.py` | Path inputs, preset profiles, advanced parameter controls |
| `components/runner.py` | Validation display, run/dry-run buttons, threaded execution |
| `components/results.py` | Folium map, plotly heatmap, elevation profile, downloads |
| `components/batch.py` | Job queue with `Job` dataclass, sequential background execution |

## Data Flow

1. User provides input directory + parameters (via any interface)
2. Python `validators.py` reads LAS headers, checks CRS/disk/memory
3. `runner.py` builds an Rscript command with all parameters
4. R engine processes tiles sequentially with checkpoint tracking
5. `progress.py` parses R log lines in real-time → progress callbacks
6. Outputs land in the output directory as GeoTIFFs + QA files
7. GUI reads outputs with rasterio/folium for interactive visualization

## Key Design Decisions

- **R for processing, Python for UX**: lidR is the most mature open-source LiDAR library. Python provides better CLI/GUI tooling.
- **Subprocess bridge**: Simpler and more robust than rpy2. The R script is a standalone CLI tool.
- **Stateful log parsing**: The `LogParser` class tracks pipeline progress by matching regex patterns against R's futile.logger output, avoiding any coupling between R and Python.
- **Checkpoint via JSON**: Simple, human-readable, and atomic (temp file → rename).
