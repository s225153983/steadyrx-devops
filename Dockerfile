# syntax=docker/dockerfile:1
# Multi-stage build. The "test" stage carries the test and analysis tools and
# is used only by Jenkins. The "runtime" stage is the small, non-root image
# that is deployed to staging and production.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Upgrade pip first so the image does not ship a pip release with known CVEs.
RUN python -m pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["pytest", "tests/unit", "tests/integration"]

FROM base AS runtime
ARG APP_VERSION=dev
ARG BUILD_SHA=local
LABEL org.opencontainers.image.title="steadyrx-api" \
      org.opencontainers.image.description="SteadyRx medicine-related falls early warning API" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${BUILD_SHA}" \
      org.opencontainers.image.source="https://github.com/s225153983/steadyrx-devops"
ENV APP_VERSION=${APP_VERSION} \
    BUILD_SHA=${BUILD_SHA} \
    DATABASE_PATH=/data/steadyrx.db
RUN useradd --create-home --uid 10001 steadyrx \
    && mkdir -p /data && chown steadyrx:steadyrx /data
COPY app ./app
USER steadyrx
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
