FROM python:3.11-slim

WORKDIR /app

# Install git (needed by GitPython and Aider)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# aider-install sets up aider-chat in the current Python environment
RUN aider-install

# Copy backend source
COPY backend/ .

# Data directory (mounted as a volume at runtime)
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
