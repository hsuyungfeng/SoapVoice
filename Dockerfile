# SoapVoice Dockerfile
# Multi-stage build for production deployment with CUDA support

# ============================================
# Stage 1: Builder - Install dependencies
# ============================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    curl \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements for build stage
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir uv && \
    uv sync --no-install-project --frozen

# ============================================
# Stage 2: Development - Full development environment
# ============================================
FROM python:3.11-slim as development

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    curl \
    git \
    libgomp1 \
    libomp-dev \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copy source code
COPY src/ ./src/
COPY tests/ ./tests/
COPY pyproject.toml ./

# Install llama-cpp-python with CUDA support
RUN pip install --no-cache-dir \
    llama-cpp-python==0.2.90 \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Development command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================
# Stage 3: Production - Optimized image (CPU only)
# ============================================
FROM python:3.11-slim as production

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    libgomp1 \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2 \
    PYTHONPATH=/app

# Copy source code
COPY --chown=appuser:appgroup src/ /app/src/
COPY --chown=appuser:appgroup pyproject.toml /app/
COPY --chown=appuser:appgroup .env.example /app/

# Create data directories
RUN mkdir -p /app/data/local_db /app/data/recordings /app/data/sessions && \
    chown -R appuser:appgroup /app/data

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================
# Stage 4: Production with GPU support
# ============================================
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 as production-gpu

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set up Python
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

# Copy pyproject.toml
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv sync --frozen

# Install llama-cpp-python with CUDA support
RUN uv pip install --no-cache-dir \
    llama-cpp-python==0.2.90 \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121

# Copy source code
COPY src/ /app/src/
COPY .env.example /app/

# Create data directories
RUN mkdir -p /app/data/local_db /app/data/recordings /app/data/sessions /app/models

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command with GPU
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
