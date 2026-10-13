# syntax=docker/dockerfile:1

# ---- app: runtime dependencies and application code, shared by both targets ----
FROM python:3.12-alpine AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    ACEEST_DB=/data/aceest_fitness.db

WORKDIR /app

# Unprivileged user; /data is the only path it can write to
RUN addgroup -S -g 10001 aceest \
    && adduser -S -u 10001 -G aceest -H aceest \
    && mkdir /data \
    && chown aceest:aceest /data

# Dependencies first so this layer is reused until requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY templates/ templates/

USER aceest

# ---- test: adds the test tooling and suite; `docker run` executes pytest ----
FROM app AS test

USER root
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY pytest.ini .
COPY tests/ tests/
USER aceest

# /app is read-only for this user, so keep pytest and coverage state out of it
ENV COVERAGE_FILE=/tmp/.coverage
CMD ["pytest", "-p", "no:cacheprovider", "--cov=app", "--cov-report=term-missing"]

# ---- runtime: the default target, served by gunicorn ----
FROM app AS runtime

EXPOSE 5000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)"]

# The control socket would need a writable home directory, which this user does not have
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "--no-control-socket", "app:create_app()"]
