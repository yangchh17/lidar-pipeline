# LiDAR Processing Pipeline

Automated terrain processing pipeline for tiled LAS/LAZ point cloud data.

**Generates:** DTM, DSM, and hillshade rasters from raw LiDAR tiles.

## Requirements

```r
install.packages(c("lidR", "terra", "argparse"))
# Optional for parallel processing:
install.packages("future")
```

## Quick Start

```bash
# Basic usage
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results

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

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
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
