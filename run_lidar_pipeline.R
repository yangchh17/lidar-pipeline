#!/usr/bin/env Rscript
# =============================================================================
# LiDAR DTM/DSM Processing Pipeline
#
# Processes tiled LAS files through:
#   1. Duplicate point filtering
#   2. CSF ground classification
#   3. DTM generation (knnidw)
#   4. DSM generation (pitfree)
#   5. Hillshade rendering
#
# Usage:
#   Rscript run_lidar_pipeline.R --input ./data/tiles --output ./results
#   Rscript run_lidar_pipeline.R --config config.yaml
#   Rscript run_lidar_pipeline.R --input ./data --output ./out --dry-run
#
# =============================================================================

suppressPackageStartupMessages({
  library(lidR)
  library(terra)
  library(tools)
  library(argparse)
  library(yaml)
})

# =============================================================================
# CLI Argument Parsing
# =============================================================================

create_parser <- function() {
  parser <- ArgumentParser(
    description = "LiDAR terrain processing pipeline: filter, classify, DTM, DSM, hillshade"
  )

  # Config file
  parser$add_argument("--config",
                      help = "YAML configuration file (CLI args override config values)")

  # Required (unless provided via config)
  parser$add_argument("--input",
                      help = "Directory containing tiled LAS/LAZ files")
  parser$add_argument("--output",
                      help = "Output directory for all results")

  # Resolution
  parser$add_argument("--resolution", type = "double", default = 0.5,
                      help = "Output raster resolution in meters [default: 0.5]")

  # CSF parameters
  parser$add_argument("--csf-cloth-res", type = "double", default = 0.6,
                      help = "CSF cloth resolution [default: 0.6]")
  parser$add_argument("--csf-threshold", type = "double", default = 0.4,
                      help = "CSF classification threshold [default: 0.4]")
  parser$add_argument("--csf-rigidness", type = "integer", default = 3L,
                      help = "CSF rigidness: 1=flat, 2=moderate, 3=steep [default: 3]")

  # Processing
  parser$add_argument("--chunk-size", type = "integer", default = 250L,
                      help = "Processing chunk size in meters [default: 250]")
  parser$add_argument("--chunk-buffer", type = "integer", default = 50L,
                      help = "Chunk buffer in meters [default: 50]")
  parser$add_argument("--cores", type = "integer", default = 1L,
                      help = "Number of parallel cores [default: 1]")

  # Hillshade
  parser$add_argument("--hillshade-angle", type = "double", default = 40.0,
                      help = "Sun elevation angle for hillshade [default: 40]")
  parser$add_argument("--hillshade-direction", type = "double", default = 270.0,
                      help = "Sun azimuth for hillshade [default: 270]")

  # Skip flags
  parser$add_argument("--skip-dtm", action = "store_true", default = FALSE,
                      help = "Skip DTM generation")
  parser$add_argument("--skip-dsm", action = "store_true", default = FALSE,
                      help = "Skip DSM generation")
  parser$add_argument("--skip-hillshade", action = "store_true", default = FALSE,
                      help = "Skip hillshade generation")

  # Modes
  parser$add_argument("--dry-run", action = "store_true", default = FALSE,
                      help = "Validate inputs and show plan without processing")

  return(parser)
}

# =============================================================================
# YAML Config Loading
# =============================================================================

# Map between YAML keys and argparse argument names
config_key_map <- list(
  input              = "input",
  output             = "output",
  resolution         = "resolution",
  csf_cloth_res      = "csf_cloth_res",
  csf_threshold      = "csf_threshold",
  csf_rigidness      = "csf_rigidness",
  chunk_size         = "chunk_size",
  chunk_buffer       = "chunk_buffer",
  cores              = "cores",
  hillshade_angle    = "hillshade_angle",
  hillshade_direction = "hillshade_direction",
  skip_dtm           = "skip_dtm",
  skip_dsm           = "skip_dsm",
  skip_hillshade     = "skip_hillshade"
)

load_config <- function(config_path) {
  if (!file.exists(config_path)) {
    cat(sprintf("✗ Config file not found: %s\n", config_path))
    quit(save = "no", status = 1)
  }

  tryCatch({
    cfg <- yaml::read_yaml(config_path)
    cat(sprintf("✓ Loaded config: %s\n", config_path))
    return(cfg)
  }, error = function(e) {
    cat(sprintf("✗ Failed to parse config: %s\n", e$message))
    quit(save = "no", status = 1)
  })
}

# Flatten nested YAML (e.g. csf.cloth_res → csf_cloth_res)
flatten_config <- function(cfg, prefix = "") {
  result <- list()
  for (key in names(cfg)) {
    full_key <- if (nzchar(prefix)) paste0(prefix, "_", key) else key
    if (is.list(cfg[[key]]) && !is.null(names(cfg[[key]]))) {
      result <- c(result, flatten_config(cfg[[key]], full_key))
    } else {
      result[[full_key]] <- cfg[[key]]
    }
  }
  return(result)
}

# Merge: config provides defaults, CLI args override
merge_config_and_args <- function(args) {
  if (is.null(args$config)) return(args)

  cfg <- load_config(args$config)
  flat <- flatten_config(cfg)

  # argparse defaults — used to detect which args the user actually set
  defaults <- list(
    resolution = 0.5, csf_cloth_res = 0.6, csf_threshold = 0.4,
    csf_rigidness = 3L, chunk_size = 250L, chunk_buffer = 50L,
    cores = 1L, hillshade_angle = 40.0, hillshade_direction = 270.0,
    skip_dtm = FALSE, skip_dsm = FALSE, skip_hillshade = FALSE
  )

  for (yaml_key in names(config_key_map)) {
    arg_name <- config_key_map[[yaml_key]]
    config_val <- flat[[yaml_key]]
    if (is.null(config_val)) next

    # Use config value only if CLI arg is NULL or still at its default
    cli_val <- args[[arg_name]]
    is_default <- !is.null(defaults[[arg_name]]) && identical(cli_val, defaults[[arg_name]])

    if (is.null(cli_val) || is_default) {
      args[[arg_name]] <- config_val
    }
  }

  return(args)
}

# =============================================================================
# Input Validation
# =============================================================================

validate_inputs <- function(args) {
  errors <- character(0)

  # Check input directory
  if (!dir.exists(args$input)) {
    errors <- c(errors, sprintf("Input directory does not exist: %s", args$input))
  } else {
    las_files <- list.files(args$input, pattern = "\\.(las|laz)$", ignore.case = TRUE)
    if (length(las_files) == 0) {
      errors <- c(errors, sprintf("No LAS/LAZ files found in: %s", args$input))
    }
  }

  # Check parameter ranges
  if (args$resolution <= 0) {
    errors <- c(errors, sprintf("Resolution must be positive, got: %.2f", args$resolution))
  }
  if (args$csf_cloth_res <= 0) {
    errors <- c(errors, "CSF cloth resolution must be positive")
  }
  if (args$csf_threshold <= 0) {
    errors <- c(errors, "CSF threshold must be positive")
  }
  if (!args$csf_rigidness %in% 1:3) {
    errors <- c(errors, "CSF rigidness must be 1 (flat), 2 (moderate), or 3 (steep)")
  }
  if (args$chunk_size <= 0) {
    errors <- c(errors, "Chunk size must be positive")
  }
  if (args$chunk_buffer < 0) {
    errors <- c(errors, "Chunk buffer cannot be negative")
  }
  if (args$cores < 1) {
    errors <- c(errors, "Cores must be >= 1")
  }

  # Report
  if (length(errors) > 0) {
    cat("✗ Validation failed:\n")
    for (e in errors) cat("  -", e, "\n")
    quit(save = "no", status = 1)
  }

  # Summary
  las_files <- list.files(args$input, pattern = "\\.(las|laz)$", ignore.case = TRUE)
  total_size_mb <- sum(file.size(file.path(args$input, las_files))) / 1024^2

  cat("✓ Validation passed\n")
  cat(sprintf("  Input:       %s (%d files, %.1f MB)\n",
              args$input, length(las_files), total_size_mb))
  cat(sprintf("  Output:      %s\n", args$output))
  cat(sprintf("  Resolution:  %.2f m\n", args$resolution))
  cat(sprintf("  CSF:         cloth_res=%.2f, threshold=%.2f, rigidness=%d\n",
              args$csf_cloth_res, args$csf_threshold, args$csf_rigidness))
  cat(sprintf("  Chunks:      %d m (buffer: %d m)\n", args$chunk_size, args$chunk_buffer))
  cat(sprintf("  Cores:       %d\n", args$cores))
  cat(sprintf("  Steps:       %s\n",
              paste(c(
                if (!args$skip_dtm) "DTM",
                if (!args$skip_dsm) "DSM",
                if (!args$skip_hillshade) "Hillshade"
              ), collapse = " → ")))
}

# =============================================================================
# Output Directory Setup
# =============================================================================

setup_output_dirs <- function(output_base) {
  dirs <- list(
    filtered   = file.path(output_base, "01_filtered"),
    classified = file.path(output_base, "02_classified"),
    dtm        = file.path(output_base, "03_dtm"),
    dsm        = file.path(output_base, "04_dsm"),
    hillshade  = file.path(output_base, "05_hillshade")
  )
  for (d in dirs) dir.create(d, showWarnings = FALSE, recursive = TRUE)
  return(dirs)
}

# =============================================================================
# Step 1: Filter Duplicate Points
# =============================================================================

filter_duplicates_per_tile <- function(las_dir, out_dir) {
  las_files <- list.files(las_dir, pattern = "\\.(las|laz)$",
                          full.names = TRUE, ignore.case = TRUE)

  cat(sprintf("\n── Step 1: Filtering duplicates (%d tiles) ──\n", length(las_files)))

  for (i in seq_along(las_files)) {
    las_path <- las_files[i]
    tile_name <- file_path_sans_ext(basename(las_path))
    out_path <- file.path(out_dir, paste0(tile_name, "_filtered.las"))

    if (file.exists(out_path)) {
      cat(sprintf("  [%d/%d] ⏭ %s (exists)\n", i, length(las_files), tile_name))
      next
    }

    tryCatch({
      las <- readLAS(las_path)
      if (is.empty(las)) {
        cat(sprintf("  [%d/%d] ⚠ %s (empty, skipped)\n", i, length(las_files), tile_name))
        next
      }
      las_filtered <- filter_duplicates(las)
      n_removed <- npoints(las) - npoints(las_filtered)
      writeLAS(las_filtered, out_path)
      cat(sprintf("  [%d/%d] ✓ %s (removed %d duplicates)\n",
                  i, length(las_files), tile_name, n_removed))
    }, error = function(e) {
      cat(sprintf("  [%d/%d] ✗ %s: %s\n", i, length(las_files), tile_name, e$message))
    })
  }
}

# =============================================================================
# Step 2: CSF Ground Classification + DTM
# =============================================================================

build_dtm <- function(filtered_dir, classified_dir, dtm_dir, args) {
  cat("\n── Step 2: Ground classification + DTM ──\n")

  ctg <- readLAScatalog(filtered_dir)
  opt_chunk_size(ctg)   <- args$chunk_size
  opt_chunk_buffer(ctg) <- args$chunk_buffer
  opt_output_files(ctg) <- file.path(classified_dir, "{ORIGINALFILENAME}_classified")

  if (args$cores > 1) {
    library(future)
    plan(multisession, workers = args$cores)
  }

  cat("  Classifying ground points (CSF)...\n")
  csf_algo <- csf(
    sloop_smooth  = FALSE,
    cloth_resolution = args$csf_cloth_res,
    class_threshold  = args$csf_threshold,
    rigidness        = args$csf_rigidness,
    iterations       = 1000L,
    time_step        = 0.65
  )
  classify_ground(ctg, csf_algo)

  cat("  Building DTM (knnidw)...\n")
  ctg_classified <- readLAScatalog(classified_dir)
  opt_chunk_size(ctg_classified)   <- args$chunk_size
  opt_chunk_buffer(ctg_classified) <- args$chunk_buffer
  opt_output_files(ctg_classified) <- file.path(dtm_dir, "dtm_tile_{XLEFT}_{YBOTTOM}")

  dtm <- rasterize_terrain(ctg_classified, res = args$resolution, algorithm = knnidw())

  dtm_merged_path <- file.path(dirname(dtm_dir), "dtm.tif")
  writeRaster(dtm, dtm_merged_path, overwrite = TRUE)
  cat(sprintf("  ✓ DTM saved: %s\n", dtm_merged_path))

  return(dtm_merged_path)
}

# =============================================================================
# Step 3: DSM
# =============================================================================

build_dsm <- function(classified_dir, dsm_dir, args) {
  cat("\n── Step 3: DSM (pitfree) ──\n")

  ctg <- readLAScatalog(classified_dir)
  opt_chunk_size(ctg)   <- args$chunk_size
  opt_chunk_buffer(ctg) <- args$chunk_buffer
  opt_output_files(ctg) <- file.path(dsm_dir, "dsm_tile_{XLEFT}_{YBOTTOM}")

  dsm <- rasterize_canopy(ctg, res = args$resolution,
                          algorithm = pitfree(thresholds = c(0, 10, 20, 30),
                                              max_edge = c(0, 1.5)))

  dsm_merged_path <- file.path(dirname(dsm_dir), "dsm.tif")
  writeRaster(dsm, dsm_merged_path, overwrite = TRUE)
  cat(sprintf("  ✓ DSM saved: %s\n", dsm_merged_path))

  return(dsm_merged_path)
}

# =============================================================================
# Step 4: Hillshade
# =============================================================================

generate_hillshade <- function(dtm_path, hillshade_dir, args) {
  cat("\n── Step 4: Hillshade ──\n")

  dtm <- rast(dtm_path)
  slope  <- terrain(dtm, v = "slope",  unit = "radians")
  aspect <- terrain(dtm, v = "aspect", unit = "radians")
  hs <- shade(slope, aspect,
              angle     = args$hillshade_angle,
              direction = args$hillshade_direction)

  hs_path <- file.path(dirname(hillshade_dir), "hillshade.tif")
  writeRaster(hs, hs_path, overwrite = TRUE)
  cat(sprintf("  ✓ Hillshade saved: %s\n", hs_path))

  return(hs_path)
}

# =============================================================================
# Main
# =============================================================================

main <- function() {
  start_time <- Sys.time()

  # Parse arguments
  parser <- create_parser()
  args <- parser$parse_args()

  # Merge YAML config (CLI args override config values)
  args <- merge_config_and_args(args)

  # Ensure required args are present (may come from config or CLI)
  if (is.null(args$input) || is.null(args$output)) {
    cat("✗ --input and --output are required (via CLI or config file)\n")
    quit(save = "no", status = 1)
  }

  cat("═══════════════════════════════════════════\n")
  cat("  LiDAR Processing Pipeline\n")
  cat("═══════════════════════════════════════════\n\n")

  # Validate
  validate_inputs(args)

  # Dry run: stop here
  if (args$dry_run) {
    cat("\n🔍 Dry run complete. No files were processed.\n")
    quit(save = "no", status = 0)
  }

  # Set up output directories
  dirs <- setup_output_dirs(args$output)

  # Step 1: Filter duplicates
  filter_duplicates_per_tile(args$input, dirs$filtered)

  # Step 2: DTM
  dtm_path <- NULL
  if (!args$skip_dtm) {
    dtm_path <- build_dtm(dirs$filtered, dirs$classified, dirs$dtm, args)
  } else {
    cat("\n── Step 2: DTM (skipped) ──\n")
  }

  # Step 3: DSM
  if (!args$skip_dsm) {
    build_dsm(dirs$classified, dirs$dsm, args)
  } else {
    cat("\n── Step 3: DSM (skipped) ──\n")
  }

  # Step 4: Hillshade
  if (!args$skip_hillshade && !is.null(dtm_path)) {
    generate_hillshade(dtm_path, dirs$hillshade, args)
  } else {
    cat("\n── Step 4: Hillshade (skipped) ──\n")
  }

  # Done
  elapsed <- as.numeric(difftime(Sys.time(), start_time, units = "mins"))
  cat("\n═══════════════════════════════════════════\n")
  cat(sprintf("  ✓ Pipeline complete (%.1f minutes)\n", elapsed))
  cat(sprintf("  Output: %s\n", args$output))
  cat("═══════════════════════════════════════════\n")
}

main()
