# Debug image for LLSS (Low Level Screen Service).
# Build context is the repo root: `docker compose -f deploy/docker-compose.yml build`.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Pillow runtime libs + fonts (LLSS does frame conversion) and ping for debug.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo \
        zlib1g \
        libfreetype6 \
        fonts-dejavu-core \
        iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Contents of app/ land in /app, matching the dev invocation `cd app && uvicorn main:app`.
COPY app/ ./
# Migrations available if ever needed (NOT auto-run; the live DB is already migrated).
COPY alembic/ ./alembic/
COPY alembic.ini ./

EXPOSE 8008

# PORT comes from the env_file (.env: PORT=8008). Shell form so ${PORT} expands.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8008}
