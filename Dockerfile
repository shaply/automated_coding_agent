FROM python:3.12-slim

WORKDIR /app

# Install git (needed by GitPython and Aider)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY backend/requirements.txt .
# aider-install (the meta-package) creates its own venv, which doesn't work in Docker.
# Instead we install aider-chat directly — the underlying package aider-install would fetch.
# For LOCAL dev outside Docker: pip install aider-install && aider-install
RUN pip install --no-cache-dir setuptools wheel
RUN pip install --no-cache-dir aider-chat
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Data directory (mounted as a volume at runtime)
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
