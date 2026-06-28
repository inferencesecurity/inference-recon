FROM python:3.12-slim

# git is required for cloning and pulling corpus repos
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies at build time.
# Source code is volume-mounted at run time — no COPY needed.
COPY eval/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Default entrypoint — override at `docker compose run` time as needed
# e.g. docker compose run --rm scanner python eval/batch_scan.py eval/corpus/repos.txt
