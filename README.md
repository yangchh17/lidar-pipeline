# LiDAR Processing Pipeline

Automated terrain processing pipeline for tiled LAS/LAZ point cloud data.

**Generates:** DTM, DSM, and hillshade rasters from raw LiDAR tiles.

> **New to LiDAR?** Check out the [Beginner's Guide](docs/GUIDE.md) — a step-by-step tutorial covering LiDAR fundamentals, setup, and how to use this pipeline from scratch.

## Requirements

```r
install.packages(c("lidR", "terra", "argparse", "yaml"))
# Optional for parallel processing:
install.packages("future")
```

## Quick Start

```bash
# Basic usage
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results

# Using a config file
cp config.example.yaml config.yaml
# Edit config.yaml with your paths and parameters
Rscript run_lidar_pipeline.R --config config.yaml

# Config + CLI override (CLI args take precedence)
Rscript run_lidar_pipeline.R --config config.yaml --resolution 1.0 --cores 8

# Custom resolution and CSF parameters
Rscript run_lidar_pipeline.R \
  --input ./data/tiles \
  --output ./results \
  --resolution 1.0 \
  --csf-rigidness 1

# Validate inputs without processing
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results --dry-run

# DTM only (skip DSM and hillshade)
Rscript run_lidar_pipeline.R \
  --input ./data/tiles \
  --output ./results \
  --skip-dsm --skip-hillshade

# Parallel processing
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results --cores 4
```

## Configuration Files

Use YAML config files to avoid repetitive CLI arguments:

1. Copy `config.example.yaml` to `config.yaml`
2. Edit paths and parameters
3. Run with `--config config.yaml`

**CLI arguments override config values**, so you can set defaults in the config and override specific parameters on the command line.

Example `config.yaml`:
```yaml
input: /data/project_2024/tiles
output: /data/project_2024/results
resolution: 0.5
cores: 8
csf:
  rigidness: 3
  threshold: 0.4
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--config` | — | YAML config file (CLI args override) |
| `--input` | (required) | Directory containing LAS/LAZ tiles |
| `--output` | (required) | Output directory |
| `--resolution` | 0.5 | Raster resolution in meters |
| `--csf-cloth-res` | 0.6 | CSF cloth resolution |
| `--csf-threshold` | 0.4 | CSF classification threshold |
| `--csf-rigidness` | 3 | 1=flat, 2=moderate, 3=steep terrain |
| `--chunk-size` | 250 | Processing chunk size (meters) |
| `--chunk-buffer` | 50 | Chunk buffer (meters) |
| `--cores` | 1 | Parallel processing cores |
| `--hillshade-angle` | 40 | Sun elevation for hillshade |
| `--hillshade-direction` | 270 | Sun azimuth for hillshade |
| `--skip-dtm` | false | Skip DTM generation |
| `--skip-dsm` | false | Skip DSM generation |
| `--skip-hillshade` | false | Skip hillshade generation |
| `--dry-run` | false | Validate only, no processing |

## Logging

All output uses structured logging via `futile.logger`:

- Console: INFO level by default, DEBUG with `--verbose`
- File: always DEBUG level, saved to `<output_dir>/pipeline.log`
- Progress bars show real-time tile processing status

```bash
# Verbose mode for debugging
Rscript run_lidar_pipeline.R --config config.yaml --verbose
```

## Output Structure

```
results/
├── 01_filtered/          # Deduplicated LAS tiles
├── 02_classified/        # Ground-classified tiles
├── 03_dtm/               # DTM raster tiles
├── 04_dsm/               # DSM raster tiles
├── 05_hillshade/         # (reserved)
├── dtm.tif               # Merged DTM
├── dsm.tif               # Merged DSM
└── hillshade.tif         # Hillshade raster
```

## Processing Steps

1. **Filter duplicates** — removes duplicate points per tile
2. **Ground classification** — CSF (Cloth Simulation Filter) algorithm
3. **DTM** — Digital Terrain Model via knnidw interpolation
4. **DSM** — Digital Surface Model via pitfree algorithm
5. **Hillshade** — shaded relief from DTM

## License

MIT
