# syntax=docker/dockerfile:1
# check=skip=FromPlatformFlagConstDisallowed

# The skipped check warns against hardcoding a platform, on the grounds that it
# blocks multi-platform builds. That is the intent here: there is exactly one
# target platform and pinning it in the file means no build can forget the flag.
#
# Build context is the repo root; see compose.yaml.
#
# Stages:
#   frontend     -- builds the Vite app to static files
#   python-base  -- interpreter, Stockfish, and the settings both Python stages share
#   builder      -- resolves the dependency venv, and is where uv lives
#   dev          -- builder + dev dependencies + reload; used by compose.override.yaml
#   runtime      -- the production image (default target)

# ---------------------------------------------------------------------------
# Frontend build.
#
# Deliberately not pinned to a platform: the output is plain JS and CSS, so
# this can run natively on whatever machine is doing the build.
# ---------------------------------------------------------------------------
FROM node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS frontend

WORKDIR /frontend

# Dependencies first, so this layer is cached until the lockfile changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Shared Python base.
#
# Pinned to amd64 because that is what the target platform runs and because the
# venv built below carries compiled wheels: an image built on an ARM machine
# would otherwise push cleanly and then die on its first start.
# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS python-base

# Stockfish is a system package, not a Python dependency, so it is installed here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*

# The engine binary is on PATH inside the image, so override any host path.
#
# PYTHONUNBUFFERED: without it, log lines sit in a buffer instead of reaching
# the container's stdout as they happen, and the log aggregator looks broken.
#
# PATH: putting the venv's entry points first is what lets the runtime stage
# exec uvicorn with no uv present to activate anything.
ENV STOCKFISH_PATH=/usr/games/stockfish \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

# This must be identical in every stage that touches the venv: the scripts in
# .venv/bin hardcode their interpreter's absolute path, so a venv built under
# one WORKDIR and copied under another breaks in a thoroughly confusing way.
WORKDIR /app

# ---------------------------------------------------------------------------
# Dependency build. uv exists only from here down; the runtime stage gets the
# venv it produced and nothing else.
# ---------------------------------------------------------------------------
FROM python-base AS builder

# Copy the standalone binary in from the official uv image.
COPY --from=ghcr.io/astral-sh/uv:0.11@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c /uv /usr/local/bin/uv

# Compile to .pyc at install time rather than making the first request pay for it.
ENV UV_COMPILE_BYTECODE=1

# Dependencies first, so this layer is cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Development. Adds the dev dependency group so pytest and ruff can run inside
# the container, and keeps uv around for changing dependencies.
# ---------------------------------------------------------------------------
FROM builder AS dev

RUN uv sync --frozen

# In dev these are shadowed by bind mounts; they are kept here so the image is
# still runnable on its own.
COPY backend ./backend
COPY data ./data

ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

EXPOSE 8000

# --host 0.0.0.0 makes the server reachable from outside the container.
CMD ["uvicorn", "backend.app.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
# Production runtime.
# ---------------------------------------------------------------------------
FROM python-base AS runtime

COPY --from=builder /app/.venv ./.venv
COPY backend ./backend
COPY data ./data
# Served by FastAPI, so the API and the app share an origin and there is no
# CORS to configure. The path matches the FRONTEND_DIST default in app.py.
COPY --from=frontend /frontend/dist ./frontend/dist

# Nothing in the image is written to at runtime, so an unprivileged user with
# no write access to /app is enough.
RUN useradd --create-home --uid 1000 appuser
USER appuser

# The repository is not in the image, so the commit the code was built from is
# passed in at build time and read back by the observability layer at runtime.
# Declared late to keep it out of the cached layers above.
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA

EXPOSE 8000

# Exec form with no shell and no `uv run` wrapper, so uvicorn is PID 1 and
# receives SIGTERM directly when the platform stops the container -- otherwise
# the signal goes to a wrapper that does not forward it and the container is
# killed after the grace period instead of shutting down.
#
# The platform terminates TLS and proxies, so trust its forwarding headers;
# without them the app sees the proxy's address and http:// for every request.
# Trusting any peer is safe here because only the platform can reach the port.
CMD ["uvicorn", "backend.app.app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
