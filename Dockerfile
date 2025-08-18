# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROMA_TELEMETRY_ENABLED=false \
    PORT=8989 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal system deps (tini for signal handling; build-essential for any wheels that need compiling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl tini ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy deps first for better layer caching
COPY requirements.txt .

# Faster, more reliable installs:
# - upgrade pip/setuptools/wheel
# - prefer binary wheels
# - use BuildKit cache for pip (speeds incremental builds)
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -U pip setuptools wheel && \
    python -m pip install --prefer-binary -r requirements.txt

# App code
COPY app ./app
COPY data ./data

# Persist Chroma locally
VOLUME ["/app/chroma_data"]

# Expose configured port (default 8989; set -e PORT=7979 to switch)
EXPOSE 8989

ENTRYPOINT ["/usr/bin/tini","-g","--"]
CMD ["sh","-lc","uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
