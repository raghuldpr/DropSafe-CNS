# ==============================================================================
# DropSafe Backend Dockerfile
# Modular Monolith - Python 3.12+ / FastAPI / SQLAlchemy 2.x
# ==============================================================================

FROM python:3.12-slim AS base

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1001 dropsafe && \
    useradd -u 1001 -g dropsafe -s /bin/bash -m dropsafe

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy source code and config
COPY . .

# Ensure storage and log directories exist and are owned by dropsafe
RUN mkdir -p /app/data/storage /app/logs && \
    chown -R dropsafe:dropsafe /app

USER dropsafe

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
