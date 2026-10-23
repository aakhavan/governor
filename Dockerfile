# governor-ask API: one container, read-only warehouse baked in, run state on /data.
#
#   docker build -t governor .
#   docker run -p 8000:8000 -v governor-data:/data --env-file .env governor
#
# See docs/deploy.md. Single-tenant portfolio deployment.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

# Build the green warehouse, harvest its metadata and write the catalog cards
# at build time, so the image carries a fixed, read-only warehouse (as_of is
# pinned in fixture/AS_OF).
RUN python fixture/build_green.py \
 && python -m governor.core.harvest artifacts/green --out artifacts/meta.duckdb \
 && python -m governor.ask.catalog build \
 && rm -rf fixture/billing_mart/target fixture/billing_mart/logs fixture/billing_mart/warehouse.duckdb logs

# Writable run state (decision traces, checkpoints) lives only in /data.
RUN useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin governor \
 && mkdir -p /data \
 && chown governor:governor /data
ENV GOVERNOR_STATE_DIR=/data
VOLUME ["/data"]

USER governor
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "governor.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
