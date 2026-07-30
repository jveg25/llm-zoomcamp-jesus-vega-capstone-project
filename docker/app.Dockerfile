# Shared image for the FastAPI backend and the Streamlit UI (same code + deps,
# different start commands set per-service in docker-compose).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first (cached unless the lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Then the application code
COPY app ./app
COPY ui ./ui
COPY ingestion ./ingestion
COPY common ./common
