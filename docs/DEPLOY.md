# Streamlit Cloud Deployment

Deploy the LiDAR Pipeline GUI to [Streamlit Community Cloud](https://streamlit.io/cloud) for free.

## Prerequisites

- GitHub repo with the pipeline code (public or connected to Streamlit Cloud)
- Streamlit Community Cloud account (free at streamlit.io)

## Limitations

Streamlit Cloud provides Python-only environments. The R engine cannot run on Streamlit Cloud directly. The deployed app will work for **visualization of pre-computed results** but cannot execute the R pipeline.

For full pipeline execution, use Docker or a local install.

## Steps

### 1. Add Streamlit config

Create `.streamlit/config.toml` in the repo root:

```toml
[server]
maxUploadSize = 200

[theme]
primaryColor = "#2E86AB"
```

### 2. Create `packages.txt` (system deps for rasterio)

```
libgdal-dev
libgeos-dev
libproj-dev
```

### 3. Deploy

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click "New app"
3. Select your repo, branch `main`, main file `app/main.py`
4. Click "Deploy"

The app will install Python dependencies from `requirements.txt` and system packages from `packages.txt` automatically.

### 4. Usage on Streamlit Cloud

Since R is not available, the app will show a friendly error if you try to run the pipeline. Use it to:
- Browse and visualize results from a pre-processed dataset
- Demonstrate the GUI to stakeholders
- Test parameter validation logic

## Full Deployment (with R)

For full pipeline execution, use Docker:

```bash
docker compose up --build
# Open http://localhost:8501
```

Or deploy the Docker image to any container platform (Railway, Render, AWS ECS, etc.).
