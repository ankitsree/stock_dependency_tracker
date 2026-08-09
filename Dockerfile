# syntax=docker/dockerfile:1
#
# Production image for the FastAPI backend (production-roadmap.md §5).
#
# Python 3.12 rather than the 3.9 the local venv floors at: nothing in the
# dependency set needs <3.11, and a modern interpreter is the right thing to
# run in production. `pyproject.toml` keeps its >=3.9 floor so local dev is
# unaffected.
#
# Note this image runs the API only. The React frontend is a separate
# deployable — a static build served by Vercel's CDN (see frontend/vercel.json).

# ---------------------------------------------------------------- builder ---
# Installs into a throwaway venv so the runtime stage inherits the packages
# without pip, its caches, or any build toolchain.
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
RUN python -m venv /opt/venv

# `pip install .` needs the package sources present, so a source edit
# invalidates the (slow) dependency layer too. Acceptable for now — if rebuild
# times start to hurt, split runtime deps into their own requirements file and
# install that in a layer above this COPY.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install .

# ---------------------------------------------------------------- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root: a container escape shouldn't start from root.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src/
COPY config.yaml ./
# Needed to run `alembic upgrade head` inside the container — e.g. as
# Render's Pre-Deploy Command (production-roadmap.md §6 step 5).
COPY alembic.ini ./
COPY migrations/ ./migrations/

# config.yaml supplies defaults only; anything environment-specific
# (CORS_ALLOWED_ORIGINS, DATABASE_URL, LOG_LEVEL) is injected at runtime.
#
# The parquet cache is a container-local scratch dir. It is deliberately NOT a
# durable store — an ephemeral filesystem loses it on every restart, which is
# exactly why Phase 4.8 moves durable state to Postgres.
RUN mkdir -p data/cache data/raw data/processed outputs/graphs outputs/reports \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

# `${PORT:-8000}` because hosts like Render and Fly assign the port via env.
# `exec` keeps uvicorn as PID 1 so it receives SIGTERM and shuts down cleanly.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT','8000'), timeout=3).status == 200 else 1)"

CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
