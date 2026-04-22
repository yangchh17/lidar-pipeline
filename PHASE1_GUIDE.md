# Phase 1 Implementation Guide - R Engine Refactoring

**Goal:** Transform `run_lidar_pipeline.R` from a hardcoded script into a production-ready CLI tool.

**Estimated Time:** 5-7 days (1-2 hours per task)

---

## Task 1.1: CLI Argument Parsing (Day 1)

### Current State
```r
# Hardcoded paths at top of script
las_input_dir <- "path/to/las_tiles"
output_base   <- "path/to/output"
```

### Target State
```bash
Rscript run_lidar_pipeline.R \
  --input ./data/tiles \
  --output ./results \
  --resolution 0.5 \
  --csf-cloth-res 0.6
```

### Implementation Steps

1. **Install argparse package**
```r
install.packages("argparse")
```

2. **Add argument parser at top of script**
```r
library(argparse)

parser <- ArgumentParser(description = "LiDAR DTM/DSM Pipeline")

# Required arguments
parser$add_argument("--input", required = TRUE,
                    help = "Directory containing tiled LAS files")
parser$add_argument("--output", required = TRUE,
                    help = "Output directory for results")

# Optional arguments with defaults
parser$add_argument("--resolution", type = "double", default = 0.5,
                    help = "Output raster resolution in meters (default: 0.5)")
parser$add_argument("--csf-cloth-res", type = "double", default = 0.6,
                    help = "CSF cloth resolution (default: 0.6)")
parser$add_argument("--csf-threshold", type = "double", default = 0.4,
                    help = "CSF classification threshold (default: 0.4)")
parser$add_argument("--csf-rigidness", type = "integer", default = 3L,
                    help = "CSF rigidness: 1=flat, 2=moderate, 3=steep (default: 3)")
parser$add_argument("--chunk-size", type = "integer", default = 250L,
                    help = "Processing chunk size in meters (default: 250)")
parser$add_argument("--chunk-buffer", type = "integer", default = 50L,
                    help = "Chunk buffer size in meters (default: 50)")
parser$add_argument("--skip-dtm", action = "store_true",
                    help = "Skip DTM generation")
parser$add_argument("--skip-dsm", action = "store_true",
                    help = "Skip DSM generation")
parser$add_argument("--dry-run", action = "store_true",
                    help = "Validate inputs without processing")

args <- parser$parse_args()
```

3. **Replace hardcoded values**
```r
# Old:
las_input_dir <- "path/to/las_tiles"
output_base   <- "path/to/output"

# New:
las_input_dir <- args$input
output_base   <- args$output
resolution    <- args$resolution

# In CSF call:
csf_algo <- csf(
  cloth_resolution = args$csf_cloth_res,
  class_threshold  = args$csf_threshold,
  rigidness        = args$csf_rigidness,
  iterations       = 1000L
)

# In catalog options:
opt_chunk_size(ctg)   <- args$chunk_size
opt_chunk_buffer(ctg) <- args$chunk_buffer
```

4. **Add input validation**
```r
validate_inputs <- function(args) {
  # Check input directory exists
  if (!dir.exists(args$input)) {
    stop("Input directory does not exist: ", args$input)
  }
  
  # Check for LAS files
  las_files <- list.files(args$input, pattern = "\\.las$", ignore.case = TRUE)
  if (length(las_files) == 0) {
    stop("No LAS files found in: ", args$input)
  }
  
  # Check resolution is positive
  if (args$resolution <= 0) {
    stop("Resolution must be positive, got: ", args$resolution)
  }
  
  # Check CSF parameters are in valid ranges
  if (args$csf_cloth_res <= 0) {
    stop("CSF cloth resolution must be positive")
  }
  if (args$csf_threshold <= 0 || args$csf_threshold > 1) {
    stop("CSF threshold must be between 0 and 1")
  }
  if (!args$csf_rigidness %in% 1:3) {
    stop("CSF rigidness must be 1, 2, or 3")
  }
  
  cat("✓ Input validation passed\n")
  cat(sprintf("  - Found %d LAS files\n", length(las_files)))
  cat(sprintf("  - Resolution: %.2f m\n", args$resolution))
  cat(sprintf("  - CSF params: cloth_res=%.2f, threshold=%.2f, rigidness=%d\n",
              args$csf_cloth_res, args$csf_threshold, args$csf_rigidness))
}

# Call at start of main()
validate_inputs(args)

if (args$dry_run) {
  cat("Dry run complete. Exiting.\n")
  quit(save = "no", status = 0)
}
```

### Testing
```bash
# Test help
Rscript run_lidar_pipeline.R --help

# Test dry run
Rscript run_lidar_pipeline.R \
  --input ./test_data \
  --output ./test_output \
  --dry-run

# Test with custom parameters
Rscript run_lidar_pipeline.R \
  --input ./test_data \
  --output ./test_output \
  --resolution 1.0 \
  --csf-cloth-res 0.8
```

### Checklist
- [ ] argparse installed and imported
- [ ] All hardcoded paths replaced with args
- [ ] All algorithm parameters exposed as CLI args
- [ ] Input validation function added
- [ ] --dry-run mode works
- [ ] --help displays all options
- [ ] Script runs with default values
- [ ] Script runs with custom values

---

## Task 1.2: Configuration File Support (Day 2)

### Goal
Allow users to save parameter sets in YAML files for reproducibility.

### Implementation

1. **Install yaml package**
```r
install.packages("yaml")
```

2. **Add config file argument**
```r
parser$add_argument("--config", 
                    help = "YAML configuration file (CLI args override config)")
```

3. **Create config loader**
```r
library(yaml)

load_config <- function(config_path) {
  if (is.null(config_path) || !file.exists(config_path)) {
    return(list())
  }
  
  config <- yaml::read_yaml(config_path)
  cat("✓ Loaded config from:", config_path, "\n")
  return(config)
}

merge_config_and_args <- function(config, args) {
  # CLI args override config file
  # For each arg, use CLI value if provided, else config value, else default
  
  if (is.null(args$input) && !is.null(config$input)) {
    args$input <- config$input
  }
  if (is.null(args$output) && !is.null(config$output)) {
    args$output <- config$output
  }
  # ... repeat for all parameters
  
  return(args)
}

# In main():
config <- load_config(args$config)
args <- merge_config_and_args(config, args)
```

4. **Create example config file**
```yaml
# config.example.yaml
# LiDAR Pipeline Configuration

# Input/Output
input: "./data/las_tiles"
output: "./results"

# Raster Resolution
resolution: 0.5  # meters

# CSF Ground Classification
csf_cloth_res: 0.6
csf_threshold: 0.4
csf_rigidness: 3  # 1=flat, 2=moderate, 3=steep

# Processing
chunk_size: 250    # meters
chunk_buffer: 50   # meters

# Output Options
skip_dtm: false
skip_dsm: false
```

### Testing
```bash
# Run with config file
Rscript run_lidar_pipeline.R --config config.yaml

# Override config with CLI args
Rscript run_lidar_pipeline.R \
  --config config.yaml \
  --resolution 1.0  # overrides config value
```

### Checklist
- [ ] yaml package installed
- [ ] --config argument added
- [ ] Config loader function works
- [ ] CLI args properly override config
- [ ] config.example.yaml created
- [ ] Tested with config file
- [ ] Tested with config + CLI override

---

## Task 1.3: Robust Error Handling & Logging (Day 3-4)

### Goal
Replace `cat()` with structured logging and handle errors gracefully.

### Implementation

1. **Install logging package**
```r
install.packages("futile.logger")
```

2. **Set up logger**
```r
library(futile.logger)

setup_logging <- function(output_dir, log_level = INFO) {
  log_file <- file.path(output_dir, "pipeline.log")
  
  # Log to both console and file
  flog.appender(appender.tee(log_file))
  flog.threshold(log_level)
  
  flog.info("=== LiDAR Pipeline Started ===")
  flog.info("Log file: %s", log_file)
  flog.info("Timestamp: %s", Sys.time())
}

# Replace all cat() calls:
# cat("Processing...") → flog.info("Processing...")
# cat("Warning:...") → flog.warn("Warning:...")
# cat("Error:...") → flog.error("Error:...")
```

3. **Add error handling to tile processing**
```r
filter_duplicates_per_tile <- function(las_dir, out_dir) {
  las_files <- list.files(las_dir, pattern = "\\.las$", full.names = TRUE)
  
  success_count <- 0
  error_count <- 0
  
  for (las_path in las_files) {
    tile_name <- file_path_sans_ext(basename(las_path))
    filtered_path <- file.path(out_dir, paste0(tile_name, "_filtered.las"))
    
    tryCatch({
      if (file.exists(filtered_path)) {
        flog.info("⏭️ Already filtered: %s", basename(filtered_path))
        success_count <- success_count + 1
        next
      }
      
      las <- safe_readLAS(las_path)
      if (is.null(las)) {
        flog.warn("⚠️ Skipped (bad or empty): %s", tile_name)
        error_count <- error_count + 1
        next
      }
      
      flog.info("🔍 Filtering duplicates for: %s", tile_name)
      writeLAS(filter_duplicates(las), filtered_path)
      flog.info("✅ Saved: %s", basename(filtered_path))
      success_count <- success_count + 1
      
    }, error = function(e) {
      flog.error("❌ Failed to process %s: %s", tile_name, e$message)
      error_count <- error_count + 1
    })
  }
  
  flog.info("Filtering complete: %d success, %d errors", success_count, error_count)
  
  if (error_count > 0 && success_count == 0) {
    stop("All tiles failed to process")
  }
}
```

4. **Add progress reporting**
```r
library(progress)

filter_duplicates_per_tile <- function(las_dir, out_dir) {
  las_files <- list.files(las_dir, pattern = "\\.las$", full.names = TRUE)
  
  pb <- progress_bar$new(
    format = "[:bar] :percent | :current/:total tiles | ETA: :eta",
    total = length(las_files),
    clear = FALSE
  )
  
  for (las_path in las_files) {
    # ... processing ...
    pb$tick()
  }
}
```

### Checklist
- [ ] futile.logger installed
- [ ] Logging set up (console + file)
- [ ] All cat() replaced with flog.*()
- [ ] Error handling added to all processing functions
- [ ] Progress bars added
- [ ] Errors logged but don't crash entire pipeline
- [ ] Summary stats logged at end

---

## Task 1.4: Checkpoint & Resume (Day 5)

### Goal
Save processing state so interrupted runs can resume.

### Implementation

1. **Create state tracker**
```r
library(jsonlite)

StateTracker <- R6::R6Class("StateTracker",
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
        flog.info("Loaded checkpoint: %d tiles completed", 
                  length(self$state$completed_tiles))
      } else {
        self$state <- list(
          started_at = as.character(Sys.time()),
          completed_tiles = list(),
          failed_tiles = list()
        )
      }
    },
    
    save = function() {
      jsonlite::write_json(self$state, self$state_file, 
                          auto_unbox = TRUE, pretty = TRUE)
    },
    
    is_completed = function(tile_name) {
      tile_name %in% self$state$completed_tiles
    },
    
    mark_completed = function(tile_name) {
      self$state$completed_tiles <- c(self$state$completed_tiles, tile_name)
      self$save()
    },
    
    mark_failed = function(tile_name, error_msg) {
      self$state$failed_tiles[[tile_name]] <- error_msg
      self$save()
    }
  )
)
```

2. **Add --resume flag**
```r
parser$add_argument("--resume", action = "store_true",
                    help = "Resume from checkpoint (skip completed tiles)")
```

3. **Use state tracker in processing**
```r
filter_duplicates_per_tile <- function(las_dir, out_dir, state = NULL, resume = FALSE) {
  las_files <- list.files(las_dir, pattern = "\\.las$", full.names = TRUE)
  
  for (las_path in las_files) {
    tile_name <- file_path_sans_ext(basename(las_path))
    
    # Check if already completed
    if (resume && !is.null(state) && state$is_completed(tile_name)) {
      flog.info("⏭️ Skipping (checkpoint): %s", tile_name)
      next
    }
    
    tryCatch({
      # ... processing ...
      
      # Mark as completed
      if (!is.null(state)) {
        state$mark_completed(tile_name)
      }
      
    }, error = function(e) {
      if (!is.null(state)) {
        state$mark_failed(tile_name, e$message)
      }
    })
  }
}

# In main():
state <- StateTracker$new(output_base)
filter_duplicates_per_tile(las_input_dir, out_dirs$filtered, 
                           state = state, resume = args$resume)
```

### Checklist
- [ ] R6 and jsonlite installed
- [ ] StateTracker class implemented
- [ ] --resume flag added
- [ ] State saved after each tile
- [ ] Resume skips completed tiles
- [ ] Failed tiles tracked separately
- [ ] Tested: interrupt and resume

---

## Task 1.5: Output Validation & QA Report (Day 6-7)

### Goal
Generate quality assurance metrics and HTML report.

### Implementation

1. **Collect QA metrics**
```r
collect_qa_metrics <- function(las_input_dir, dtm_path, dsm_path, state) {
  metrics <- list(
    timestamp = as.character(Sys.time()),
    input = list(
      directory = las_input_dir,
      tile_count = length(list.files(las_input_dir, pattern = "\\.las$")),
      total_points = 0  # calculate from tiles
    ),
    processing = list(
      completed_tiles = length(state$state$completed_tiles),
      failed_tiles = length(state$state$failed_tiles),
      processing_time_seconds = 0  # track in main()
    ),
    outputs = list()
  )
  
  # DTM metrics
  if (file.exists(dtm_path)) {
    dtm <- rast(dtm_path)
    metrics$outputs$dtm <- list(
      path = dtm_path,
      resolution = res(dtm)[1],
      extent = as.list(ext(dtm)),
      crs = crs(dtm),
      valid_pixels = global(dtm, "notNA")[1,1],
      elevation_min = global(dtm, "min", na.rm = TRUE)[1,1],
      elevation_max = global(dtm, "max", na.rm = TRUE)[1,1],
      elevation_mean = global(dtm, "mean", na.rm = TRUE)[1,1],
      elevation_sd = global(dtm, "sd", na.rm = TRUE)[1,1]
    )
  }
  
  # DSM metrics (similar)
  
  return(metrics)
}
```

2. **Generate HTML report**
```r
library(rmarkdown)

generate_qa_report <- function(metrics, output_dir) {
  report_path <- file.path(output_dir, "qa_report.html")
  
  # Create R Markdown content
  rmd_content <- sprintf('
---
title: "LiDAR Pipeline QA Report"
date: "%s"
output: html_document
---

## Processing Summary

- **Input Directory:** `%s`
- **Tiles Processed:** %d / %d
- **Failed Tiles:** %d
- **Processing Time:** %.1f minutes

## DTM Statistics

- **Resolution:** %.2f m
- **Valid Pixels:** %d
- **Elevation Range:** %.2f - %.2f m
- **Mean Elevation:** %.2f m
- **Std Dev:** %.2f m

## DSM Statistics

(similar)

## Hillshade Preview

![DTM Hillshade](dtm_hillshade.png)

## Failed Tiles

%s
',
    metrics$timestamp,
    metrics$input$directory,
    metrics$processing$completed_tiles,
    metrics$input$tile_count,
    metrics$processing$failed_tiles,
    metrics$processing$processing_time_seconds / 60,
    metrics$outputs$dtm$resolution,
    metrics$outputs$dtm$valid_pixels,
    metrics$outputs$dtm$elevation_min,
    metrics$outputs$dtm$elevation_max,
    metrics$outputs$dtm$elevation_mean,
    metrics$outputs$dtm$elevation_sd,
    if (length(metrics$processing$failed_tiles) > 0) {
      paste("- ", names(metrics$processing$failed_tiles), collapse = "\n")
    } else {
      "None"
    }
  )
  
  # Write and render
  rmd_file <- file.path(output_dir, "qa_report.Rmd")
  writeLines(rmd_content, rmd_file)
  rmarkdown::render(rmd_file, output_file = report_path, quiet = TRUE)
  
  flog.info("QA report generated: %s", report_path)
}
```

3. **Save hillshade preview**
```r
save_hillshade_preview <- function(dtm_path, output_dir) {
  dtm <- rast(dtm_path)
  slope <- terrain(dtm, v = "slope", unit = "radians")
  aspect <- terrain(dtm, v = "aspect", unit = "radians")
  hs <- shade(slope, aspect, angle = 40, direction = 315)
  
  png_path <- file.path(output_dir, "dtm_hillshade.png")
  png(png_path, width = 1600, height = 1200, res = 150)
  plot(hs, col = gray.colors(256), legend = FALSE, axes = FALSE, 
       main = "DTM Hillshade")
  dev.off()
  
  flog.info("Hillshade preview saved: %s", png_path)
}
```

### Checklist
- [ ] QA metrics collection function
- [ ] HTML report generation
- [ ] Hillshade preview PNG
- [ ] Report includes all key stats
- [ ] Failed tiles listed in report
- [ ] Report opens in browser automatically (optional)

---

## Final Integration

### Updated main() function structure

```r
main <- function() {
  start_time <- Sys.time()
  
  # 1. Parse arguments
  args <- parser$parse_args()
  config <- load_config(args$config)
  args <- merge_config_and_args(config, args)
  
  # 2. Set up logging
  dir.create(args$output, showWarnings = FALSE, recursive = TRUE)
  setup_logging(args$output)
  
  # 3. Validate inputs
  validate_inputs(args)
  if (args$dry_run) {
    flog.info("Dry run complete. Exiting.")
    quit(save = "no", status = 0)
  }
  
  # 4. Initialize state tracker
  state <- StateTracker$new(args$output)
  
  # 5. Create output directories
  out_dirs <- list(
    filtered   = file.path(args$output, "filtered_las"),
    classified = file.path(args$output, "classified_las"),
    dtm_dir    = file.path(args$output, "dtm"),
    dsm_dir    = file.path(args$output, "dsm")
  )
  invisible(lapply(out_dirs, dir.create, showWarnings = FALSE, recursive = TRUE))
  
  # 6. Process
  filter_duplicates_per_tile(args$input, out_dirs$filtered, state, args$resume)
  
  if (!args$skip_dtm) {
    dtm_path <- file.path(args$output, "dtm.tif")
    build_dtm(out_dirs$filtered, out_dirs$classified, out_dirs$dtm_dir, 
              dtm_path, args)
    save_hillshade_preview(dtm_path, args$output)
  }
  
  if (!args$skip_dsm) {
    dsm_path <- file.path(args$output, "dsm.tif")
    build_dsm(out_dirs$classified, out_dirs$dsm_dir, dsm_path, args)
  }
  
  # 7. Generate QA report
  end_time <- Sys.time()
  processing_time <- as.numeric(difftime(end_time, start_time, units = "secs"))
  
  metrics <- collect_qa_metrics(args$input, dtm_path, dsm_path, state)
  metrics$processing$processing_time_seconds <- processing_time
  
  generate_qa_report(metrics, args$output)
  
  flog.info("=== Pipeline Complete ===")
  flog.info("Total time: %.1f minutes", processing_time / 60)
}
```

---

## Testing Checklist

### Unit Tests
- [ ] Argument parsing with various inputs
- [ ] Config file loading and merging
- [ ] Input validation (valid/invalid paths, parameters)
- [ ] State tracker save/load
- [ ] QA metrics calculation

### Integration Tests
- [ ] Full pipeline with small test dataset
- [ ] Resume from checkpoint
- [ ] Skip DTM/DSM flags
- [ ] Error handling (corrupted LAS file)
- [ ] Config file + CLI override

### Performance Tests
- [ ] Process 1GB dataset
- [ ] Memory usage monitoring
- [ ] Processing time benchmarks

---

## Documentation Updates

After completing Phase 1, update:

1. **README.md** - Add CLI usage examples
2. **CHANGELOG.md** - Document new features
3. **config.example.yaml** - Provide template
4. **CONTRIBUTING.md** - Development setup guide

---

## Ready to Start?

Begin with Task 1.1 (CLI arguments). Commit after each task:

```bash
git checkout -b feature/phase1-refactoring
# ... work on Task 1.1 ...
git add run_lidar_pipeline.R
git commit -m "feat: add CLI argument parsing"
git push origin feature/phase1-refactoring
```

Let me know when you're ready to dive in!
