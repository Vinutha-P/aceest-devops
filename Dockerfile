# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# ACEest Fitness & Gym - multi-stage image
#   base    : runtime dependencies only
#   test    : base + dev dependencies + tests  (CI runs pytest inside this)
#   runtime : small, non-root production image (default target)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- test stage: used by Jenkins to run pytest inside the container ----------
FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["python", "-m", "pytest", "--junitxml=reports/junit-container.xml", \
     "--cov=aceest", "--cov-report=xml:reports/coverage-container.xml"]

# ---------- runtime stage: what gets pushed to Docker Hub ----------
FROM base AS runtime
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="aceest-fitness" \
      org.opencontainers.image.description="ACEest Fitness & Gym Flask application" \
      org.opencontainers.image.version="${APP_VERSION}"
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data && chown appuser:appuser /data
COPY --chown=appuser:appuser aceest/ aceest/
COPY --chown=appuser:appuser ACEest_Fitness.py gunicorn.conf.py ./
USER appuser
ENV PORT=5000 \
    ACEEST_DB=/data/aceest_fitness.db
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)" || exit 1
CMD ["gunicorn", "--config", "gunicorn.conf.py", "ACEest_Fitness:app"]
