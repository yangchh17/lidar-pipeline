# Quickstart Guide

Get the LiDAR pipeline running in 5 minutes.

## 1. Install R dependencies

```r
install.packages(c("lidR", "terra", "argparse", "yaml",
                    "futile.logger", "R6", "jsonlite", "progress"))
```

Verify: `Rscript -e "library(lidR); cat('OK\n')"`

## 2. Install Python package

```bash
cd lidar-pipeline
pip install -e .
```

## 3. Prepare your data

Put your LAS/LAZ tiles in a single directory:

```
data/
├── tile_001.las
├── tile_002.las
└── tile_003.las
```

All tiles should share the same CRS (coordinate reference system).

## 4a. Run via GUI

```bash
streamlit run app/main.py
```

1. Enter your input directory path in the sidebar
2. Enter an output directory path
3. Pick a preset (Balanced is a good default)
4. Click "Run Pipeline"
5. Switch to the Results tab when done

## 4b. Run via CLI

```bash
# Basic run
lidar-pipeline --input ./data --output ./results

# With custom resolution
lidar-pipeline --input ./data --output ./results --resolution 1.0

# Dry run (validate only)
lidar-pipeline --input ./data --output ./results --dry-run
```

## 5. Check results

```
results/
├── dtm.tif              # Open in QGIS or ArcGIS
├── dsm.tif
├── hillshade.tif
├── dtm_hillshade.png    # Quick visual check
└── qa_report.html       # Open in browser
```

## Tips

- Start with `--resolution 1.0` for faster test runs, then go to 0.5 or 0.25 for production
- Use `--cores 4` (or more) if you have the RAM — roughly 2GB per core
- Use `--resume` if a run gets interrupted
- CSF rigidness: use 1 for flat terrain, 3 for mountains

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Rscript not found` | Install R and add to PATH |
| `Error in library(lidR)` | Run `install.packages("lidR")` in R |
| `No LAS files found` | Check the input path and file extensions (.las or .laz) |
| `CRS mismatch` | Reproject tiles to a common CRS with `las2las` or PDAL |
| `Out of memory` | Reduce `--cores` or `--chunk-size` |
| `Permission denied` on output | Check write permissions on the output directory |
