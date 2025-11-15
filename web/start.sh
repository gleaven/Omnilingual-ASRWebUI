#!/bin/bash

# Omnilingual ASR Web Interface Startup Script

set -e

echo "========================================="
echo "  Omnilingual ASR Web Interface"
echo "========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if models are downloaded
MODEL_DIR="$HOME/.cache/fairseq2/assets"
if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A $MODEL_DIR)" ]; then
    echo "⚠️  Warning: ASR models not found in $MODEL_DIR"
    echo ""
    echo "Would you like to download the models now? (This will take ~5-10GB)"
    read -p "Download models? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📥 Downloading models..."
        cd ../repo
        python download_all_models.py
        cd ../web
        echo "✅ Models downloaded successfully"
    else
        echo "⚠️  Skipping model download. You can download later with:"
        echo "   cd repo && python download_all_models.py"
    fi
    echo ""
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
fi

# Start services
echo "🚀 Starting services..."
echo ""
echo "This will start:"
echo "  - PostgreSQL database (port 5432)"
echo "  - Redis (port 6379)"
echo "  - FastAPI backend (internal only)"
echo "  - Celery worker"
echo "  - Web frontend + API (port 8123)"
echo ""

# Build and start containers
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "========================================="
    echo "✅ All services started successfully!"
    echo "========================================="
    echo ""
    echo "📱 Access the web interface at:"
    echo "   http://localhost:8123"
    echo ""
    echo "📚 API documentation at:"
    echo "   http://localhost:8123/docs"
    echo ""
    echo "📊 View logs with:"
    echo "   docker-compose logs -f"
    echo ""
    echo "🛑 Stop services with:"
    echo "   docker-compose down"
    echo ""
else
    echo ""
    echo "❌ Error: Some services failed to start"
    echo "Check logs with: docker-compose logs"
    exit 1
fi
