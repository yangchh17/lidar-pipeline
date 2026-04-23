# LiDAR Processing Pipeline

Automated terrain processing pipeline for tiled LAS/LAZ point cloud data. Generates DTM, DSM, and hillshade rasters from raw LiDAR tiles.

Includes a production-ready R engine, a Python CLI wrapper, and a Streamlit web GUI.

> **New to LiDAR?** Check out the [Beginner's Guide](docs/GUIDE.md) for fundamentals and a step-by-step tutorial.

## Features

- **R engine** — lidR-based processing with CSF ground classification, pitfree DSM, knnidw DTM
- **Python CLI** — input validation, real-time progress bars, structured JSON output
- **Streamlit GUI** — parameter presets, interactive maps, batch job queue, download buttons
- **Checkpoint & resume** — interrupt and restart without reprocessing completed tiles
- **QA reporting** — automated metrics, hillshade previews, HTML summary

## Quick Start

### Option 1: Streamlit GUI

```bash
pip install -e .
streamlit run app/main.py
```

Open the browser, set input/output paths, pick a preset, and click Run.

### Option 2: Python CLI

```bash
pip install -e .
lidar-pipeline --input ./data/tiles --output ./results
lidar-pipeline --input ./data/tiles --output ./results --resolution 1.0 --cores 4
lidar-pipeline --input ./data/tiles --output ./results --dry-run
```

### Option 3: R engine directly

```bash
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results
Rscript run_lidar_pipeline.R --config config.yaml
Rscript run_lidar_pipeline.R --config config.yaml --resolution 1.0 --cores 8
```

## Installation

### Prerequisites

- **R** ≥ 4.2 with packages: `lidR`, `terra`, `argparse`, `yaml`, `futile.logger`, `R6`, `jsonlite`
- **Python** ≥ 3.10

### Install R packages

```r
install.packages(c("lidR", "terra", "argparse", "yaml", "futile.logger", "R6", "jsonlite", "progress"))
```

### Install Python package

```bash
git clone https://github.com/yangchh/lidar-pipeline.git
cd lidar-pipeline
pip install -e .
```

## Configuration

Use YAML config files to save parameter sets:

```bash
cp config.example.yaml config.yaml
# Edit paths and parameters, then:
Rscript run_lidar_pipeline.R --config config.yaml
```

CLI arguments always override config file values.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--input` | (required) | Directory containing LAS/LAZ tiles |
| `--output` | (required) | Output directory |
| `--config` | — | YAML config file |
| `--resolution` | 0.5 | Raster cell size in meters |
| `--csf-cloth-res` | 0.6 | CSF cloth resolution |
| `--csf-threshold` | 0.4 | CSF classification threshold |
| `--csf-rigidness` | 3 | 1=flat, 2=moderate, 3=steep |
| `--chunk-size` | 250 | Processing chunk size (m) |
| `--chunk-buffer` | 50 | Chunk overlap buffer (m) |
| `--cores` | 1 | Parallel processing cores |
| `--hillshade-angle` | 40 | Sun elevation angle (°) |
| `--hillshade-direction` | 270 | Sun azimuth (°) |
| `--skip-dtm` | false | Skip DTM generation |
| `--skip-dsm` | false | Skip DSM generation |
| `--skip-hillshade` | false | Skip hillshade generation |
| `--resume` | false | Resume from checkpoint |
| `--dry-run` | false | Validate only |
| `--verbose` | false | Debug-level logging |

## Output Structure

```
results/
├── 01_filtered/          # Deduplicated LAS tiles
├── 02_classified/        # Ground-classified tiles
├── 03_dtm/               # DTM raster tiles
├── 04_dsm/               # DSM raster tiles
├── dtm.tif               # Merged DTM
├── dsm.tif               # Merged DSM
├── hillshade.tif         # Hillshade raster
├── dtm_hillshade.png     # Quick preview
├── qa_report.html        # QA summary
├── qa_metrics.json       # Machine-readable metrics
└── pipeline.log          # Processing log
```

## Processing Steps

1. **Filter duplicates** — removes duplicate points per tile
2. **Ground classification** — CSF (Cloth Simulation Filter) algorithm
3. **DTM generation** — Digital Terrain Model via knnidw interpolation
4. **DSM generation** — Digital Surface Model via pitfree algorithm
5. **Hillshade** — shaded relief visualization from DTM
6. **QA report** — elevation stats, coverage metrics, preview images

## GUI Screenshots

The Streamlit GUI provides:

- Sidebar with parameter presets (Fast / Balanced / Accurate) and advanced mode
- Run tab with input validation, progress tracking, and error suggestions
- Results tab with interactive elevation heatmap, geographic map overlay, elevation profile, and download buttons
- Batch tab for queuing multiple processing jobs

## Testing

```bash
pip install pytest
pytest tests/ -v
```

32 unit tests covering validators, progress parser, runner command builder, and CLI integration.

## Project Structure

```
lidar-pipeline/
├── run_lidar_pipeline.R       # R engine (production CLI)
├── config.example.yaml        # Example configuration
├── lidar_pipeline/            # Python package
│   ├── cli.py                 # Click CLI wrapper
│   ├── runner.py              # R subprocess runner
│   ├── validators.py          # Input validation (laspy)
│   └── progress.py            # Real-time log parser + tqdm
├── app/                       # Streamlit GUI
│   ├── main.py                # App entry point
│   └── components/
│       ├── sidebar.py         # Parameters + presets
│       ├── runner.py          # Run tab + progress
│       ├── results.py         # Visualization + downloads
│       └── batch.py           # Job queue
├── tests/                     # Unit tests
└── docs/
    └── GUIDE.md               # Beginner's guide
```

## License

MIT
