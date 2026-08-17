# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Build stage: compile wheels so the runtime image needs no toolchain.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# libcairo2 + pango: SVG logo rasterisation for PNG exports.
# fonts-dejavu-core: QR caption rendering.
# libpq5: PostgreSQL client library.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpq5 \
        fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin linkhub

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=linkhub:linkhub . .

# Media lives outside the application directory so an uploaded file can never be
# served as, or mistaken for, application code.
RUN mkdir -p /var/lib/linkhub/media && chown -R linkhub:linkhub /var/lib/linkhub \
    && chmod +x /app/entrypoint.sh

USER linkhub

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
