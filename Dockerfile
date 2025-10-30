# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system deps (if wheels unavailable, keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose default dev port (Railway will pass $PORT at runtime)
EXPOSE 8000

# Default command (Railway overrides with startCommand from railway.json)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
