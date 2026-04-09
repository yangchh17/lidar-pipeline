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
  library(futile.logger)
  library(progress)
  library(R6)
  library(jsonlite)
})

# =============================================================================
# State Tracker (Checkpoint & Resume)
# =============================================================================

StateTracker <- R6Class("StateTracker",
  public = list(
    state_file = NULL,
    state = list(),
    
    initialize = function(output_dir) {
      self$state_file <- file.path(output_dir, ".pipeline_state.json")
      self$load()
    },
    
    load = function() {
      if (file.exists(self$state_file)) {
        self$state <- jsonlite::read_json(self$state_file)
        flog.info("Loaded checkpoint: %d tiles completed, %d steps done",
                  length(self$state$completed_tiles),
                  length(self$state$completed_steps))
      } else {
        self$state <- list(
          started_at = as.character(Sys.time()),
          completed_tiles = list(),
          failed_tiles = list(),
          completed_steps = list()
        )
      }
    },
    
    save = function() {
      jsonlite::write_json(self$state, self$state_file,
                          auto_unbox = TRUE, pretty = TRUE)
    },
    
    is_tile_completed = function(tile_name) {
      tile_name %in% self$state$completed_tiles
    },
    
    mark_tile_completed = function(tile_name) {
      self$state$completed_tiles <- c(self$state$completed_tiles, tile_name)
      self$save()
    },
    
    mark_tile_failed = function(tile_name, error_msg) {
      self$state$failed_tiles[[tile_name]] <- error_msg
      self$save()
    },
    
    is_step_completed = function(step_name) {
      step_name %in% self$state$completed_steps
    },
    
    mark_step_completed = function(step_name) {
      self$state$completed_steps <- c(self$state$completed_steps, step_name)
      self$save()
    }
  )
)

# =============================================================================
# Logging Setup
# =============================================================================

setup_logging <- function(output_dir, verbose = FALSE) {
  # Console: INFO by default, DEBUG if verbose
  console_level <- if (verbose) DEBUG else INFO
  flog.threshold(console_level)

  # Console layout: clean format
  flog.layout(layout.format("~l [~t] ~m"), name = "ROOT")

  # File logger: always DEBUG level, writes to output_dir/pipeline.log
  log_file <- file.path(output_dir, "pipeline.log")
  flog.appender(appender.tee(log_file))
  flog.threshold(DEBUG)

  flog.info("Log file: %s", log_file)
  invisible(log_file)
}

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
  parser$add_argument("--resume", action = "store_true", default = FALSE,
                      help = "Resume from checkpoint (skip completed tiles/steps)")
  parser$add_argument("--verbose", action = "store_true", default = FALSE,
                      help = "Enable verbose (DEBUG level) console logging")

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
  skip_hillshade     = "skip_hillshade",
  verbose            = "verbose"
)

load_config <- function(config_path) {
  if (!file.exists(config_path)) {
    flog.error("Config file not found: %s", config_path)
    quit(save = "no", status = 1)
  }

  tryCatch({
    cfg <- yaml::read_yaml(config_path)
    flog.info("Loaded config: %s", config_path)
    return(cfg)
  }, error = function(e) {
    flog.error("Failed to parse config: %s", e$message)
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
    skip_dtm = FALSE, skip_dsm = FALSE, skip_hillshade = FALSE,
    verbose = FALSE
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
    flog.error("Validation failed:")
    for (e in errors) flog.error("  - %s", e)
    quit(save = "no", status = 1)
  }

  # Summary
  las_files <- list.files(args$input, pattern = "\\.(las|laz)$", ignore.case = TRUE)
  total_size_mb <- sum(file.size(file.path(args$input, las_files))) / 1024^2

  flog.info("Validation passed")
  flog.info("  Input:       %s (%d files, %.1f MB)",
            args$input, length(las_files), total_size_mb)
  flog.info("  Output:      %s", args$output)
  flog.info("  Resolution:  %.2f m", args$resolution)
  flog.info("  CSF:         cloth_res=%.2f, threshold=%.2f, rigidness=%d",
            args$csf_cloth_res, args$csf_threshold, args$csf_rigidness)
  flog.info("  Chunks:      %d m (buffer: %d m)", args$chunk_size, args$chunk_buffer)
  flog.info("  Cores:       %d", args$cores)
  flog.info("  Steps:       %s",
            paste(c(
              if (!args$skip_dtm) "DTM",
              if (!args$skip_dsm) "DSM",
              if (!args$skip_hillshade) "Hillshade"
            ), collapse = " → "))
}
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
  flog.debug("Output directories created in: %s", output_base)
  return(dirs)
}

# =============================================================================
# Step 1: Filter Duplicate Points
# =============================================================================

filter_duplicates_per_tile <- function(las_dir, out_dir, state = NULL, resume = FALSE) {
  las_files <- list.files(las_dir, pattern = "\\.(las|laz)$",
                          full.names = TRUE, ignore.case = TRUE)
  n <- length(las_files)

  flog.info("Step 1: Filtering duplicates (%d tiles)", n)

  pb <- progress_bar$new(
    format = "  Filtering [:bar] :current/:total | :elapsed",
    total = n, clear = FALSE, width = 60
  )

  success <- 0L
  skipped <- 0L
  failed  <- 0L

  for (i in seq_along(las_files)) {
    las_path <- las_files[i]
    tile_name <- file_path_sans_ext(basename(las_path))
    out_path <- file.path(out_dir, paste0(tile_name, "_filtered.las"))

    # Checkpoint: skip already-completed tiles on resume
    if (resume && !is.null(state) && state$is_tile_completed(tile_name)) {
      flog.debug("  Skip (checkpoint): %s", tile_name)
      skipped <- skipped + 1L
      pb$tick()
      next
    }

    if (file.exists(out_path)) {
      flog.debug("  Skip (exists): %s", tile_name)
      skipped <- skipped + 1L
      pb$tick()
      next
    }

    tryCatch({
      las <- readLAS(las_path)
      if (is.empty(las)) {
        flog.warn("  Empty tile skipped: %s", tile_name)
        skipped <- skipped + 1L
        pb$tick()
        next
      }
      las_filtered <- filter_duplicates(las)
      n_removed <- npoints(las) - npoints(las_filtered)
      writeLAS(las_filtered, out_path)
      flog.debug("  Filtered: %s (removed %d duplicates)", tile_name, n_removed)
      success <- success + 1L

      # Mark tile as completed in checkpoint
      if (!is.null(state)) state$mark_tile_completed(tile_name)

    }, error = function(e) {
      flog.error("  Failed: %s - %s", tile_name, e$message)
      failed <- failed + 1L

      # Track failed tile
      if (!is.null(state)) state$mark_tile_failed(tile_name, e$message)
    })
    pb$tick()
  }

  flog.info("  Step 1 done: %d filtered, %d skipped, %d failed", success, skipped, failed)
}

# =============================================================================
# Step 2: CSF Ground Classification + DTM
# =============================================================================

build_dtm <- function(filtered_dir, classified_dir, dtm_dir, args) {
  flog.info("Step 2: Ground classification + DTM")

  ctg <- readLAScatalog(filtered_dir)
  opt_chunk_size(ctg)   <- args$chunk_size
  opt_chunk_buffer(ctg) <- args$chunk_buffer
  opt_output_files(ctg) <- file.path(classified_dir, "{ORIGINALFILENAME}_classified")

  if (args$cores > 1) {
    library(future)
    plan(multisession, workers = args$cores)
  }

  flog.info("  Classifying ground points (CSF)...")
  csf_algo <- csf(
    sloop_smooth  = FALSE,
    cloth_resolution = args$csf_cloth_res,
    class_threshold  = args$csf_threshold,
    rigidness        = args$csf_rigidness,
    iterations       = 1000L,
    time_step        = 0.65
  )
  classify_ground(ctg, csf_algo)

  flog.info("  Building DTM (knnidw)...")
  ctg_classified <- readLAScatalog(classified_dir)
  opt_chunk_size(ctg_classified)   <- args$chunk_size
  opt_chunk_buffer(ctg_classified) <- args$chunk_buffer
  opt_output_files(ctg_classified) <- file.path(dtm_dir, "dtm_tile_{XLEFT}_{YBOTTOM}")

  dtm <- rasterize_terrain(ctg_classified, res = args$resolution, algorithm = knnidw())

  dtm_merged_path <- file.path(dirname(dtm_dir), "dtm.tif")
  writeRaster(dtm, dtm_merged_path, overwrite = TRUE)
  flog.info("  DTM saved: %s", dtm_merged_path)

  return(dtm_merged_path)
}

# =============================================================================
# Step 3: DSM
# =============================================================================

build_dsm <- function(classified_dir, dsm_dir, args) {
  flog.info("Step 3: DSM (pitfree)")

  ctg <- readLAScatalog(classified_dir)
  opt_chunk_size(ctg)   <- args$chunk_size
  opt_chunk_buffer(ctg) <- args$chunk_buffer
  opt_output_files(ctg) <- file.path(dsm_dir, "dsm_tile_{XLEFT}_{YBOTTOM}")

  dsm <- rasterize_canopy(ctg, res = args$resolution,
                          algorithm = pitfree(thresholds = c(0, 10, 20, 30),
                                              max_edge = c(0, 1.5)))

  dsm_merged_path <- file.path(dirname(dsm_dir), "dsm.tif")
  writeRaster(dsm, dsm_merged_path, overwrite = TRUE)
  flog.info("  DSM saved: %s", dsm_merged_path)

  return(dsm_merged_path)
}

# =============================================================================
# Step 4: Hillshade
# =============================================================================

generate_hillshade <- function(dtm_path, hillshade_dir, args) {
  flog.info("Step 4: Hillshade")

  dtm <- rast(dtm_path)
  slope  <- terrain(dtm, v = "slope",  unit = "radians")
  aspect <- terrain(dtm, v = "aspect", unit = "radians")
  hs <- shade(slope, aspect,
              angle     = args$hillshade_angle,
              direction = args$hillshade_direction)

  hs_path <- file.path(dirname(hillshade_dir), "hillshade.tif")
  writeRaster(hs, hs_path, overwrite = TRUE)
  flog.info("  Hillshade saved: %s", hs_path)

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

  # Set up output directories (needed before logging)
  dirs <- setup_output_dirs(args$output)

  # Set up logging
  setup_logging(args$output, args$verbose)

  # Validate
  validate_inputs(args)

  # Dry run: stop here
  if (args$dry_run) {
    flog.info("Dry run complete. No files were processed.")
    quit(save = "no", status = 0)
  }

  # Initialize state tracker
  state <- StateTracker$new(args$output)
  resume <- args$resume

  if (resume) {
    flog.info("Resume mode enabled")
  }

  # Step 1: Filter duplicates
  if (resume && state$is_step_completed("filter")) {
    flog.info("Step 1: Filtering duplicates (skipped — checkpoint)")
  } else {
    filter_duplicates_per_tile(args$input, dirs$filtered, state = state, resume = resume)
    state$mark_step_completed("filter")
  }

  # Step 2: DTM
  dtm_path <- NULL
  if (!args$skip_dtm) {
    if (resume && state$is_step_completed("dtm")) {
      flog.info("Step 2: Ground classification + DTM (skipped — checkpoint)")
      dtm_path <- file.path(args$output, "dtm.tif")
    } else {
      dtm_path <- build_dtm(dirs$filtered, dirs$classified, dirs$dtm, args)
      state$mark_step_completed("dtm")
    }
  } else {
    flog.info("Step 2: DTM (skipped — user flag)")
  }

  # Step 3: DSM
  if (!args$skip_dsm) {
    if (resume && state$is_step_completed("dsm")) {
      flog.info("Step 3: DSM (skipped — checkpoint)")
    } else {
      build_dsm(dirs$classified, dirs$dsm, args)
      state$mark_step_completed("dsm")
    }
  } else {
    flog.info("Step 3: DSM (skipped — user flag)")
  }

  # Step 4: Hillshade
  if (!args$skip_hillshade && !is.null(dtm_path)) {
    if (resume && state$is_step_completed("hillshade")) {
      flog.info("Step 4: Hillshade (skipped — checkpoint)")
    } else {
      generate_hillshade(dtm_path, dirs$hillshade, args)
      state$mark_step_completed("hillshade")
    }
  } else {
    flog.info("Step 4: Hillshade (skipped)")
  }

  # Done
  elapsed <- as.numeric(difftime(Sys.time(), start_time, units = "mins"))
  flog.info("Pipeline complete (%.1f minutes)", elapsed)
  flog.info("Output: %s", args$output)
}

main()
