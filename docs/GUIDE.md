# LiDAR Processing Pipeline — Beginner's Guide

A friendly, step-by-step guide for GIS newcomers who want to process LiDAR data into terrain products (DTM, DSM, hillshade). No prior LiDAR experience required.

---

## Table of Contents

1. [What is LiDAR?](#1-what-is-lidar)
2. [Key Concepts](#2-key-concepts)
3. [Prerequisites](#3-prerequisites)
4. [Getting Sample Data](#4-getting-sample-data)
5. [Running the Pipeline](#5-running-the-pipeline)
6. [Understanding the Output](#6-understanding-the-output)
7. [Viewing Results in QGIS](#7-viewing-results-in-qgis)
8. [Configuration Tips](#8-configuration-tips)
9. [Troubleshooting & FAQ](#9-troubleshooting--faq)
10. [Further Reading](#10-further-reading)

---

## 1. What is LiDAR?

**LiDAR** (Light Detection and Ranging) is a remote sensing technology that uses laser pulses to measure distances to the Earth's surface. Think of it as a laser scanner mounted on an airplane, drone, or vehicle that fires millions of laser beams at the ground and records how long each beam takes to bounce back.

### How it works

```
  ✈️ Aircraft / Drone
   │
   │  Laser pulse fired ↓
   │
   ▼  Pulse hits tree canopy → first return
   🌲
   │  Pulse continues through gaps ↓
   │
   ▼  Pulse hits ground → last return
  ═══ Ground surface
```

Each laser pulse can generate multiple **returns**:
- **First return** — the first thing the laser hits (treetops, rooftops)
- **Last return** — typically the ground surface (the laser passes through vegetation gaps)
- **Intermediate returns** — branches, understory, etc.

### What you get: Point Clouds

The result is a **point cloud** — millions of 3D points (X, Y, Z coordinates), each representing a location where a laser pulse bounced back. Point clouds are stored in **LAS** or **LAZ** (compressed) files.

A single LiDAR survey can contain billions of points. To make processing manageable, data is usually divided into rectangular **tiles** (e.g., 500m × 500m).

### Common applications

| Field | Use Case |
|-------|----------|
| Terrain mapping | High-resolution elevation models |
| Forestry | Tree height, canopy density, biomass estimation |
| Flood modeling | Identifying flood-prone areas from terrain shape |
| Urban planning | 3D city models, building footprints |
| Archaeology | Discovering hidden structures under forest canopy |
| Mining & construction | Stockpile volume measurement |

---

## 2. Key Concepts

Before running the pipeline, here are the terms you'll encounter:

### DTM (Digital Terrain Model)

A raster (grid) representing the **bare ground surface** — with buildings, trees, and other objects removed. Think of it as "what the ground looks like if you stripped away everything on top."

```
Raw point cloud:        DTM (ground only):
  🌲  🏠                 
 ·····▪▪····            ───────────────
──────────────          Smooth ground surface
  Ground                
```

### DSM (Digital Surface Model)

A raster representing the **top of everything** — including trees, buildings, and other features. It's the "first thing you'd see from above."

```
DSM includes:           DTM includes:
🌲 treetops             ✗ removed
🏠 rooftops             ✗ removed
═══ ground              ✓ ground only
```

### DEM (Digital Elevation Model)

A general term that can refer to either DTM or DSM. In practice, people often use "DEM" to mean DTM.

### Hillshade

A visualization technique that simulates sunlight hitting the terrain surface, creating shadows and highlights. It makes flat elevation data look 3D and is much easier to interpret visually than raw elevation values.

```
Elevation grid (hard to read):     Hillshade (intuitive):
┌────────────────┐                 ┌────────────────┐
│ 342 344 347 351│                 │ ░░▒▒▓▓████▓▓▒▒│
│ 340 343 348 355│                 │ ░░▒▒▓▓████████│
│ 338 341 350 360│                 │ ░░▒▒▓▓████████│
└────────────────┘                 └────────────────┘
  Numbers only                       "Oh, that's a hill!"
```

### Ground Classification (CSF)

Raw LiDAR points include everything — ground, trees, buildings, power lines, birds. Before creating a DTM, we need to figure out which points are **ground** and which are **not ground**.

This pipeline uses the **CSF (Cloth Simulation Filter)** algorithm. Imagine draping a cloth over an inverted point cloud — the cloth settles on the ground points:

```
Step 1: Flip the point cloud upside down
Step 2: Drop a virtual cloth on top
Step 3: The cloth drapes over the (inverted) ground surface
Step 4: Points near the cloth = ground ✓
         Points far from cloth = not ground ✗
```

Key CSF parameters:
- **Rigidness** (1-3): How stiff the cloth is. Use 1 for flat terrain, 3 for steep/mountainous terrain.
- **Cloth resolution**: Grid size of the cloth. Smaller = more detail but slower.
- **Threshold**: Distance threshold for classifying a point as ground.

### Resolution

The pixel size of output rasters, in the same unit as your data's coordinate system (usually meters). A resolution of `0.5` means each pixel represents a 0.5m × 0.5m area on the ground.

| Resolution | Detail | File Size | Processing Time |
|-----------|--------|-----------|-----------------|
| 0.25m | Very high | Large | Slow |
| 0.5m | High (default) | Medium | Moderate |
| 1.0m | Medium | Small | Fast |
| 2.0m | Low | Very small | Very fast |

---

## 3. Prerequisites

### Install R

This pipeline runs on **R** (version 4.0+).

- **Windows**: Download from [https://cran.r-project.org/](https://cran.r-project.org/)
- **macOS**: `brew install r` (with Homebrew) or download from CRAN
- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt update
  sudo apt install r-base r-base-dev libgdal-dev libproj-dev libgeos-dev libudunits2-dev
  ```

### Install R packages

Open R (or RStudio) and run:

```r
install.packages(c(
  "lidR",           # LiDAR processing engine
  "terra",          # Raster operations
  "argparse",       # CLI argument parsing
  "yaml",           # Config file support
  "futile.logger",  # Logging
  "R6",             # State tracking (checkpoint/resume)
  "jsonlite",       # JSON I/O
  "rmarkdown"       # QA report generation (optional)
))

# Optional: for parallel processing
install.packages("future")
```

> **Note:** `lidR` and `terra` may take a few minutes to install as they compile from source on Linux/macOS. On Linux, make sure you have the system libraries listed above (`libgdal-dev`, etc.).

### Clone the repository

```bash
git clone https://github.com/yangchh17/lidar-pipeline.git
cd lidar-pipeline
```

---

## 4. Getting Sample Data

You need LiDAR point cloud files (`.las` or `.laz`) to run the pipeline. Here are some free sources:

### Option A: OpenTopography (Recommended for beginners)

1. Go to [https://opentopography.org/](https://opentopography.org/)
2. Click **"Find Data"**
3. Draw a small area on the map (start small — a few km²)
4. Select a dataset and download the point cloud tiles
5. Place the `.laz` files in a folder (e.g., `./data/tiles/`)

### Option B: USGS 3DEP (US data)

1. Visit [https://apps.nationalmap.gov/downloader/](https://apps.nationalmap.gov/downloader/)
2. Search for "Lidar Point Cloud (LPC)"
3. Select an area and download

### Option C: Government open data portals

Many regions publish free LiDAR data:
- **British Columbia, Canada**: [LidarBC](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/lidarbc)
- **United Kingdom**: [Environment Agency](https://environment.data.gov.uk/DefraDataDownload/?Mode=survey)
- **Netherlands**: [AHN](https://www.ahn.nl/)
- **Australia**: [Elvis](https://elevation.fsdf.org.au/)

### How much data to start with

For your first run, keep it small:
- **2–5 tiles** is plenty for testing
- Each tile is typically 10–100 MB
- Total processing time: a few minutes for small datasets

Place your `.las` or `.laz` files in a single directory:

```
data/
└── tiles/
    ├── tile_001.laz
    ├── tile_002.laz
    └── tile_003.laz
```

---

## 5. Running the Pipeline

### Basic run

```bash
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results
```

That's it! The pipeline will:
1. **Filter duplicate points** in each tile
2. **Classify ground points** using the CSF algorithm
3. **Generate DTM** (bare ground elevation)
4. **Generate DSM** (surface elevation including trees/buildings)
5. **Generate hillshade** (3D-looking terrain visualization)

### Dry run (validate without processing)

Not sure if your data is set up correctly? Run a dry run first:

```bash
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results --dry-run
```

This checks that your input files exist and parameters are valid, without actually processing anything.

### Using a config file

For repeated use, create a config file instead of typing all parameters every time:

```bash
cp config.example.yaml my_config.yaml
```

Edit `my_config.yaml`:

```yaml
input: ./data/tiles
output: ./results
resolution: 0.5
cores: 4

csf:
  rigidness: 3        # 3 for mountainous terrain
  cloth_res: 0.6
  threshold: 0.4
```

Run with:

```bash
Rscript run_lidar_pipeline.R --config my_config.yaml
```

### Parallel processing

Speed things up by using multiple CPU cores:

```bash
# Use 4 cores
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results --cores 4
```

### Resuming after interruption

If the pipeline crashes or you need to stop it, use `--resume` to pick up where you left off:

```bash
# First run (interrupted at tile 50 of 200)
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results

# Resume — skips already-completed tiles
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results --resume
```

### Skip specific steps

Don't need all outputs? Skip what you don't need:

```bash
# DTM only (skip DSM and hillshade)
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results \
  --skip-dsm --skip-hillshade

# DTM + DSM, no hillshade
Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results \
  --skip-hillshade
```

---

## 6. Understanding the Output

After a successful run, your output directory looks like this:

```
results/
├── 01_filtered/          # Deduplicated LAS tiles
│   ├── tile_001.las
│   └── tile_002.las
├── 02_classified/        # Ground-classified tiles
│   ├── tile_001.las      # Points now have ground/non-ground labels
│   └── tile_002.las
├── 03_dtm/               # DTM raster per tile
│   ├── tile_001.tif
│   └── tile_002.tif
├── 04_dsm/               # DSM raster per tile
│   ├── tile_001.tif
│   └── tile_002.tif
├── 05_hillshade/         # (reserved for future use)
├── dtm.tif               # ⭐ Merged DTM (all tiles combined)
├── dsm.tif               # ⭐ Merged DSM (all tiles combined)
├── hillshade.tif         # ⭐ Merged hillshade
├── pipeline.log          # Processing log
├── qa_metrics.json       # Quality metrics (JSON)
└── qa_report.html        # Quality report (open in browser)
```

### What to look at first

- **`hillshade.tif`** — Open this first! It's the most visually intuitive output. You'll immediately see terrain features like ridges, valleys, and slopes.
- **`qa_report.html`** — Open in your browser for a summary of processing results, statistics, and a preview image.
- **`dtm.tif`** / **`dsm.tif`** — The actual elevation data for analysis.

### File formats

All raster outputs are **GeoTIFF** (`.tif`) — a standard geospatial raster format that works with virtually every GIS software. The files contain:
- Elevation values (in the same vertical unit as your input data, usually meters)
- Coordinate reference system (CRS) information
- Georeferencing (so the raster aligns correctly on a map)

---

## 7. Viewing Results in QGIS

[QGIS](https://qgis.org/) is a free, open-source GIS application. Here's how to view your results:

### Install QGIS

Download from [https://qgis.org/download/](https://qgis.org/download/) (available for Windows, macOS, Linux).

### Open your results

1. Launch QGIS
2. Go to **Layer → Add Layer → Add Raster Layer**
3. Browse to your output directory and select `hillshade.tif`
4. Click **Add** — you should see a shaded terrain map

### Style the DTM with a color ramp

1. Add `dtm.tif` as a raster layer
2. Right-click the layer → **Properties → Symbology**
3. Change "Render type" to **Singleband pseudocolor**
4. Choose a color ramp (try **"Spectral"** reversed, or **"RdYlGn"**)
5. Click **Classify** → **OK**

Now your DTM shows elevation as colors (blue = low, red = high).

### Overlay hillshade for a 3D effect

A common technique is to overlay the colored DTM on top of the hillshade:

1. Make sure `hillshade.tif` is below `dtm.tif` in the layer panel
2. Select the `dtm.tif` layer
3. In **Properties → Symbology**, set the **Blending mode** to **"Multiply"**
4. Reduce **Opacity** to about 60-70%

This creates a beautiful 3D-looking colored terrain map.

---

## 8. Configuration Tips

### Choosing CSF parameters for your terrain

| Terrain Type | Rigidness | Cloth Resolution | Threshold |
|-------------|-----------|-----------------|-----------|
| Flat (prairies, farmland) | 1 | 0.5 | 0.5 |
| Moderate (rolling hills) | 2 | 0.6 | 0.4 |
| Steep (mountains, cliffs) | 3 | 0.6 | 0.4 |

When in doubt, start with the defaults (rigidness=3, cloth_res=0.6, threshold=0.4) — they work well for most terrain.

### Choosing resolution

- **0.25m**: Use when you need maximum detail (small areas, engineering surveys)
- **0.5m** (default): Good balance of detail and performance for most projects
- **1.0m**: Use for large areas or when you need faster processing
- **2.0m+**: Use for regional-scale analysis or quick previews

### Memory considerations

LiDAR processing is memory-intensive. As a rough guide:
- **8 GB RAM**: Can handle most tile-by-tile processing
- **16 GB RAM**: Comfortable for larger tiles and higher resolution
- **32 GB+ RAM**: Needed for very dense point clouds or merging many tiles

If you run out of memory, try:
- Processing fewer tiles at a time
- Using a coarser resolution (e.g., 1.0m instead of 0.5m)
- Reducing `--chunk-size`

---

## 9. Troubleshooting & FAQ

### "Error: package 'lidR' is not available"

Your R version may be too old. `lidR` requires R ≥ 4.0. Check with:
```r
R.version.string
```

On Linux, you may also need system libraries:
```bash
sudo apt install libgdal-dev libproj-dev libgeos-dev libudunits2-dev
```

### "Error in las_check: CRS is NA"

Your LAS files don't have a coordinate reference system defined. This is common with older datasets. You can assign one in R:

```r
library(lidR)
las <- readLAS("your_file.las")
st_crs(las) <- 26910  # Example: UTM Zone 10N (NAD83)
writeLAS(las, "your_file_with_crs.las")
```

Check with your data provider for the correct CRS/EPSG code.

### "Processing is very slow"

- Use `--cores 4` (or however many CPU cores you have) for parallel processing
- Start with a coarser resolution (`--resolution 1.0`)
- Process a subset of tiles first to estimate total time
- Check that you're not running out of RAM (which causes disk swapping)

### "Output rasters have gaps/holes"

This usually means some tiles failed during processing. Check:
- `pipeline.log` for error messages
- `qa_report.html` for failed tile details
- Re-run with `--resume` to retry failed tiles

### Can I use .laz (compressed) files?

Yes! The pipeline handles both `.las` and `.laz` files automatically. No need to decompress.

### What coordinate system should my data be in?

The pipeline works with any projected coordinate system (UTM, State Plane, etc.). It does **not** work well with geographic coordinates (latitude/longitude) because resolution is specified in meters.

If your data is in lat/lon (EPSG:4326), reproject it first using LAStools or `lidR`:
```r
library(lidR)
las <- readLAS("input.las")
las <- st_transform(las, 26910)  # Reproject to UTM Zone 10N
writeLAS(las, "output_utm.las")
```

### How do I know which EPSG code to use?

Look up your area at [https://epsg.io/](https://epsg.io/). For common regions:
- **British Columbia**: EPSG:3005 (BC Albers) or UTM zones 7-11
- **US West Coast**: EPSG:26910 (UTM 10N) or EPSG:26911 (UTM 11N)
- **UK**: EPSG:27700 (British National Grid)

---

## 10. Further Reading

### LiDAR fundamentals
- [NOAA — What is LiDAR?](https://oceanservice.noaa.gov/facts/lidar.html) — Simple 2-minute overview
- [GIS Geography — LiDAR Guide](https://gisgeography.com/lidar-light-detection-and-ranging/) — Comprehensive intro with diagrams

### R packages used in this pipeline
- [lidR documentation](https://r-lidar.github.io/lidRbook/) — The official lidR book (free online), covers everything from reading LAS files to advanced analysis
- [terra documentation](https://rspatial.github.io/terra/) — Raster processing in R

### Free LiDAR data sources
- [OpenTopography](https://opentopography.org/) — Global LiDAR data portal
- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) — US nationwide LiDAR coverage
- [LidarBC](https://www2.gov.bc.ca/gov/content/data/geographic-data-services/lidarbc) — British Columbia, Canada

### GIS software
- [QGIS](https://qgis.org/) — Free, open-source GIS (recommended for viewing results)
- [CloudCompare](https://www.cloudcompare.org/) — Free 3D point cloud viewer (great for exploring raw LAS files)

---

*This guide is part of the [LiDAR Processing Pipeline](https://github.com/yangchh17/lidar-pipeline) project. Questions or suggestions? Open an issue on GitHub.*
