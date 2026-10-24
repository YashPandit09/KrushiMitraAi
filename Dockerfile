# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# 1. Build the React frontend
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# 2. Runtime: FastAPI serves the API and the built frontend from one origin
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-compile -r backend/requirements.txt

COPY backend/__init__.py backend/__init__.py
COPY backend/app backend/app
COPY data/processed data/processed
COPY --from=frontend /src/frontend/dist frontend/dist

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health', timeout=4)" || exit 1

# FORWARDED_ALLOW_IPS (read by uvicorn) controls which proxies may set X-Forwarded-For.
CMD ["sh", "-c", "exec uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port \"${PORT}\" --proxy-headers --no-server-header"]
