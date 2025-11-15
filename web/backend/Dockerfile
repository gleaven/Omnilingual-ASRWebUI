FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install omnilingual_asr from the repo (will be mounted)
# We'll install it after the container starts to use the mounted volume
# Note: omnilingual_asr repo will be mounted as volume at /app/repo

# Copy application code
COPY backend/app /app/app

# Create storage directories
RUN mkdir -p /app/storage/{raw,processed,chunks,temp,youtube}

# Expose port
EXPOSE 8123

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV STORAGE_PATH=/app/storage
ENV DATABASE_URL=postgresql://omniasr:omniasr@db:5432/omniasr
ENV PYTHONPATH=/app/repo/src:$PYTHONPATH

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"]
