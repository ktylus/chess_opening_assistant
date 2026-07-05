FROM python:3.12-slim

# Copy the standalone binary in from the official uv image.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

# Stockfish is a system package, not a Python dependency, so it is installed here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so this layer is cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend ./backend
COPY data ./data

# The engine binary is on PATH inside the image, so override any host path.
ENV STOCKFISH_PATH=/usr/games/stockfish

EXPOSE 8000

# --host 0.0.0.0 makes the server reachable from outside the container.
CMD ["uv", "run", "--no-sync", "uvicorn", "backend.app.app:app", \
     "--host", "0.0.0.0", "--port", "8000", "--reload"]
