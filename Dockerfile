FROM rocker/r-ver:4.3.2

# System dependencies for R spatial packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev libgeos-dev libproj-dev libudunits2-dev \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# R packages
RUN R -e "install.packages(c('lidR','terra','argparse','yaml','futile.logger','R6','jsonlite','progress'), repos='https://cloud.r-project.org')"

WORKDIR /app
COPY . .

# Python environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -e .

EXPOSE 8501

CMD ["streamlit", "run", "app/main.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
