# LiDAR Pipeline Modernization - Project Roadmap

**Project Goal:** Transform the R-based LiDAR processing pipeline into a production-ready tool with modern GUI, suitable for portfolio showcase and client delivery.

**Target Users:**
- GIS consultants (self-service processing)
- First Nations communities (environmental monitoring)
- Environmental consulting firms (terrain analysis)

**Tech Stack:**
- **Core Engine:** R + lidR (proven, robust)
- **GUI:** Python + Streamlit (modern, deployable)
- **Integration:** subprocess/rpy2 for R-Python bridge
- **Deployment:** Docker + Streamlit Cloud (optional)

---

## Phase 1: Core R Engine Refactoring (Week 1)

**Goal:** Make the R script production-ready with CLI interface and robust error handling.

### Tasks:

#### 1.1 CLI Argument Parsing
- [ ] Add `argparse` or `optparse` for command-line arguments
- [ ] Parameters to expose:
  - Input/output paths
  - Resolution (DTM/DSM)
  - CSF parameters (cloth_resolution, class_threshold, rigidness)
  - Chunk size/buffer
  - Output formats (GeoTIFF, LAZ, etc.)
- [ ] Add `--help` documentation
- [ ] Add `--dry-run` mode (validate inputs without processing)

**Deliverable:** `run_lidar_pipeline.R` accepts CLI args like:
```bash
Rscript run_lidar_pipeline.R \
  --input ./data/tiles \
  --output ./results \
  --resolution 0.5 \
  --csf-cloth-res 0.6 \
  --csf-threshold 0.4
```

#### 1.2 Configuration File Support
- [ ] Add YAML/JSON config file option
- [ ] Config schema: paths, algorithm params, output options
- [ ] CLI args override config file values
- [ ] Example config: `config.example.yaml`

**Deliverable:** Can run with `--config pipeline_config.yaml`

#### 1.3 Robust Error Handling & Logging
- [ ] Replace `cat()` with proper logging (log4r or futile.logger)
- [ ] Log levels: DEBUG, INFO, WARN, ERROR
- [ ] Structured log output (timestamp, level, message)
- [ ] Graceful failure handling:
  - Skip corrupted tiles, log error, continue
  - Validate CRS consistency across tiles
  - Check disk space before writing
- [ ] Progress reporting (% complete, ETA)

**Deliverable:** Logs to file + console, handles errors gracefully

#### 1.4 Checkpoint & Resume
- [ ] Save processing state to JSON (which tiles completed)
- [ ] `--resume` flag to skip already-processed tiles
- [ ] Atomic writes (temp file → rename) to avoid partial outputs

**Deliverable:** Can resume interrupted runs without reprocessing

#### 1.5 Output Validation & QA Report
- [ ] Generate QA metrics:
  - Point counts (raw, filtered, ground-classified)
  - DTM/DSM coverage (% valid pixels)
  - Elevation range, mean, std dev
  - Processing time per tile
- [ ] Output QA report as JSON + HTML summary
- [ ] Optional: hillshade PNG for quick visual check

**Deliverable:** `qa_report.html` with stats and preview images

---

## Phase 2: Python CLI Wrapper (Week 2)

**Goal:** Create a Python wrapper that calls the R engine, providing a cleaner interface for GUI integration.

### Tasks:

#### 2.1 Python CLI Script
- [ ] Create `lidar_pipeline.py` with Click or argparse
- [ ] Wraps R script via subprocess
- [ ] Validates inputs before calling R
- [ ] Parses R output/logs and displays progress
- [ ] Returns structured results (JSON)

**Deliverable:** Python CLI that mirrors R functionality

#### 2.2 Input Validation Module
- [ ] Check LAS file validity (laspy)
- [ ] Verify CRS consistency
- [ ] Estimate memory requirements
- [ ] Warn if disk space insufficient
- [ ] Validate parameter ranges

**Deliverable:** `validators.py` module

#### 2.3 Progress Monitoring
- [ ] Parse R log output in real-time
- [ ] Display progress bar (tqdm)
- [ ] Estimate time remaining
- [ ] Handle R script crashes gracefully

**Deliverable:** Live progress feedback during processing

---

## Phase 3: Streamlit GUI (Week 3-4)

**Goal:** Build an intuitive web-based GUI for non-technical users.

### Tasks:

#### 3.1 Basic UI Layout
- [ ] File upload widget (drag-and-drop LAS files)
- [ ] Or directory picker (for local deployment)
- [ ] Parameter configuration panel (collapsible sections)
- [ ] Run button + progress indicator
- [ ] Results display area

**Deliverable:** Basic functional UI

#### 3.2 Interactive Parameter Configuration
- [ ] Preset profiles (Fast/Balanced/Accurate)
- [ ] Advanced mode: expose all CSF/rasterization params
- [ ] Tooltips explaining each parameter
- [ ] Real-time validation (red/green indicators)

**Deliverable:** User-friendly parameter tuning

#### 3.3 Results Visualization
- [ ] Interactive map (folium or plotly) showing:
  - DTM hillshade
  - DSM
  - Processing extent
- [ ] Elevation profile tool (click to draw line)
- [ ] Statistics dashboard (point counts, coverage, etc.)
- [ ] Download buttons (GeoTIFF, LAZ, QA report)

**Deliverable:** Rich results visualization

#### 3.4 Batch Processing
- [ ] Queue multiple jobs
- [ ] Job status table (pending/running/complete/failed)
- [ ] Email notification on completion (optional)

**Deliverable:** Multi-job management

#### 3.5 Error Handling & User Feedback
- [ ] Clear error messages (not stack traces)
- [ ] Suggestions for common issues:
  - "CRS mismatch detected → reproject to EPSG:XXXX?"
  - "Low memory → reduce chunk size or resolution"
- [ ] Logs viewer (expandable section)

**Deliverable:** User-friendly error handling

---

## Phase 4: Documentation & Packaging (Week 5)

**Goal:** Make the tool easy to install, use, and deploy.

### Tasks:

#### 4.1 User Documentation
- [ ] README with installation instructions
- [ ] Quickstart guide (5-minute tutorial)
- [ ] Parameter reference (what each setting does)
- [ ] Troubleshooting guide
- [ ] Example datasets (small test files)

**Deliverable:** Comprehensive docs

#### 4.2 Developer Documentation
- [ ] Code architecture diagram
- [ ] API reference (if exposing REST API)
- [ ] Contributing guide
- [ ] Testing guide

**Deliverable:** Developer-friendly docs

#### 4.3 Deployment Options
- [ ] **Local:** Docker Compose (R + Python + Streamlit)
- [ ] **Cloud:** Streamlit Cloud deployment guide
- [ ] **Desktop:** PyInstaller bundle (optional)
- [ ] Environment setup scripts (conda/venv)

**Deliverable:** Multiple deployment paths

#### 4.4 Testing
- [ ] Unit tests for Python validators
- [ ] Integration tests (small LAS dataset)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Performance benchmarks

**Deliverable:** Automated testing

---

## Phase 5: Portfolio Integration (Week 6)

**Goal:** Showcase the tool on your portfolio website.

### Tasks:

#### 5.1 Demo Page
- [ ] Add project page to yangchh.github.io
- [ ] Embedded demo (iframe to deployed Streamlit app)
- [ ] Or: video walkthrough + screenshots
- [ ] Technical write-up:
  - Problem statement
  - Solution architecture
  - Key algorithms (CSF, pitfree)
  - Results & validation

**Deliverable:** Portfolio project page

#### 5.2 Case Study
- [ ] Process real dataset (BC terrain)
- [ ] Before/after visualizations
- [ ] Quantitative results (accuracy, performance)
- [ ] Client-facing report template

**Deliverable:** Professional case study

#### 5.3 GitHub Polish
- [ ] Clean commit history
- [ ] Proper branching (main/dev)
- [ ] Release tags (v1.0.0)
- [ ] GitHub Pages docs site
- [ ] Social preview image

**Deliverable:** Professional GitHub repo

---

## Optional Enhancements (Future)

### Advanced Features
- [ ] Cloud-optimized processing (AWS Batch, Google Earth Engine)
- [ ] Multi-temporal analysis (change detection)
- [ ] Machine learning classification (random forest for land cover)
- [ ] 3D visualization (Potree, Cesium)
- [ ] REST API for programmatic access

### Integrations
- [ ] QGIS plugin
- [ ] ArcGIS Pro toolbox
- [ ] Export to common formats (LAS, LAZ, E57, PLY)

---

## Timeline Summary

| Phase | Duration | Key Deliverable |
|-------|----------|-----------------|
| 1. R Engine Refactoring | 1 week | Production-ready CLI |
| 2. Python Wrapper | 1 week | Python interface |
| 3. Streamlit GUI | 2 weeks | Web-based GUI |
| 4. Documentation & Packaging | 1 week | Deployment-ready |
| 5. Portfolio Integration | 1 week | Public showcase |
| **Total** | **6 weeks** | **Complete tool + portfolio piece** |

---

## Success Metrics

- [ ] Processes 1GB LAS dataset in <10 minutes (on standard laptop)
- [ ] Zero manual path editing required (all via GUI/CLI)
- [ ] Non-technical user can run pipeline without documentation
- [ ] Deployable to Streamlit Cloud in <5 minutes
- [ ] Portfolio page gets positive feedback from hiring managers

---

## Next Steps

1. Review this roadmap and adjust priorities
2. Set up development environment (R + Python + dependencies)
3. Create feature branch: `git checkout -b feature/modernization`
4. Start with Phase 1, Task 1.1 (CLI args)
5. Commit frequently, push to GitHub

**Ready to start?** Let me know if you want to adjust anything, or we can dive into Phase 1 right now.
