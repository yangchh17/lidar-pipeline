# run_lidar_pipeline.R
# Minimal LiDAR pipeline:
# - Filter duplicates per tile
# - Ground classify (CSF) with original params
# - DTM (0.5 m) via knnidw(k=12, p=2) + hillshade
# - DSM (0.5 m) via pitfree
# Author: Chenghao Yang
# License: MIT (suggested)

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(lidR)
  library(dplyr)
  library(readr)
  library(tools)
})

# -----------------------------
# 0) INPUTS — EDIT THESE PATHS
# -----------------------------
# Folder with tiled .las files (keep .las to match original behavior)
las_input_dir <- "path/to/las_tiles"

# Main output directory
output_base   <- "path/to/output"

# Subfolders (kept simple; names match intent)
out_dirs <- list(
  filtered   = file.path(output_base, "filtered_las"),
  classified = file.path(output_base, "classified_las"),
  dtm_dir    = file.path(output_base, "dtm_tin_05"),
  dsm_dir    = file.path(output_base, "dsm_pf_05"),
  chm_dir    = file.path(output_base, "chm_pf_05") # reserved for future
)

dir.create(output_base, showWarnings = FALSE, recursive = TRUE)
invisible(lapply(out_dirs, dir.create, showWarnings = FALSE, recursive = TRUE))

# -----------------------------
# Helpers
# -----------------------------
log_info <- function(...) cat(paste0(format(Sys.time(), "[%H:%M:%S] "), ..., "\n"))

safe_readLAS <- function(path) {
  las <- try(readLAS(path), silent = TRUE)
  if (inherits(las, "try-error") || is.null(las) || npoints(las) == 0) return(NULL)
  las
}

# -----------------------------
# 1) Preprocessing: Per-tile duplicate filtering
# -----------------------------
filter_duplicates_per_tile <- function(las_dir, out_dir) {
  las_files <- list.files(las_dir, pattern = "\\.las$", full.names = TRUE)
  if (length(las_files) == 0) stop("No .las files found in: ", las_dir)
  
  for (las_path in las_files) {
    tile_name <- file_path_sans_ext(basename(las_path))
    filtered_path <- file.path(out_dir, paste0(tile_name, "_filtered.las"))
    
    if (file.exists(filtered_path)) {
      log_info("⏭️ Already filtered: ", basename(filtered_path))
      next
    }
    
    las <- safe_readLAS(las_path)
    if (is.null(las)) {
      log_info("⚠️ Skipped (bad or empty): ", tile_name)
      next
    }
    
    log_info("🔍 Filtering duplicates for: ", tile_name)
    writeLAS(filter_duplicates(las), filtered_path)
    log_info("✅ Saved: ", basename(filtered_path))
  }
}

# -----------------------------
# 2) Ground classification + DTM + Hillshade
# -----------------------------
build_dtm <- function(filtered_dir, classified_dir, dtm_out_dir, dtm_path_out) {
  ctg <- readLAScatalog(filtered_dir)
  opt_chunk_size(ctg)   <- 250   # original values
  opt_chunk_buffer(ctg) <- 50
  opt_output_files(ctg) <- file.path(classified_dir, "{XLEFT}_{YBOTTOM}_classified")
  
  # CSF parameters (unchanged)
  csf_algo <- csf(
    cloth_resolution = 0.6,
    class_threshold  = 0.4,
    rigidness        = 3L,
    iterations       = 1000L
  )
  
  log_info("🧭 Classifying ground with CSF...")
  classify_ground(ctg, csf_algo)
  
  log_info("🧩 Rasterizing DTM (0.5 m, knnidw k=12 p=2)...")
  dtm <- rasterize_terrain(ctg, res = 0.5, algorithm = knnidw(k = 12, p = 2))
  
  dir.create(dtm_out_dir, showWarnings = FALSE, recursive = TRUE)
  writeRaster(dtm, dtm_path_out, overwrite = TRUE)
  log_info("💾 DTM written: ", dtm_path_out)
  
  # Terrain derivatives + hillshade (same parameters)
  slope  <- terrain(dtm, v = "slope",  unit = "radians")
  aspect <- terrain(dtm, v = "aspect", unit = "radians")
  hs <- shade(slope, aspect, angle = 40, direction = 315)
  
  # Quick QA plot (optional)
  plot(hs, col = gray.colors(256), legend = FALSE, axes = FALSE, main = "DTM Hillshade")
  
  invisible(list(dtm = dtm, hillshade = hs))
}

# -----------------------------
# 3) DSM (pitfree) from all points
# -----------------------------
build_dsm <- function(classified_dir, dsm_out_dir, dsm_path_out) {
  ctg_dsm <- readLAScatalog(classified_dir)
  opt_chunk_size(ctg_dsm)   <- 250
  opt_chunk_buffer(ctg_dsm) <- 50
  
  # Include all points (matches original intent)
  opt_filter(ctg_dsm) <- ""
  
  log_info("🌲 Building DSM (pitfree, 0.5 m)...")
  dsm <- rasterize_canopy(
    ctg_dsm, res = 0.5,
    algorithm = pitfree(
      thresholds = seq(0, 60, by = 5),
      subcircle  = 0.2
    )
  )
  
  dir.create(dsm_out_dir, showWarnings = FALSE, recursive = TRUE)
  writeRaster(dsm, dsm_path_out, overwrite = TRUE)
  log_info("💾 DSM written: ", dsm_path_out)
  
  invisible(dsm)
}

# -----------------------------
# 4) Orchestrate
# -----------------------------
main <- function() {
  # A) Filter duplicates
  filter_duplicates_per_tile(las_input_dir, out_dirs$filtered)
  
  # B) Ground classify + DTM + hillshade
  dtm_tif <- file.path(output_base, "dtm.tif")
  build_dtm(
    filtered_dir   = out_dirs$filtered,
    classified_dir = out_dirs$classified,
    dtm_out_dir    = out_dirs$dtm_dir,
    dtm_path_out   = dtm_tif
  )
  
  # C) DSM (pitfree)
  dsm_tif <- file.path(output_base, "dsm.tif")
  build_dsm(
    classified_dir = out_dirs$classified,
    dsm_out_dir    = out_dirs$dsm_dir,
    dsm_path_out   = dsm_tif
  )
  
  log_info("✅ All done.")
}

if (sys.nframe() == 0) main()
