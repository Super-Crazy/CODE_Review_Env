# ── Code Review OpenEnv – Dockerfile ──────────────────────────────────────────
# Deployable to Hugging Face Spaces as a containerized OpenEnv environment.
# Constraints: 2 vCPU, 8 GB RAM
FROM python:3.11-slim

# Metadata
LABEL maintainer="openenv-hackathon"
LABEL description="Code Review RL Environment – OpenEnv Hackathon Submission"
LABEL org.opencontainers.image.title="code-review-env"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY models.py      ./models.py
COPY tasks.py       ./tasks.py
COPY grader.py      ./grader.py
COPY openenv.yaml   ./openenv.yaml
COPY server/        ./server/

# Expose the FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment defaults (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENABLE_WEB_INTERFACE=true

# Launch the FastAPI server
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
