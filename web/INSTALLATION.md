# Installation & Deployment Guide

Complete guide for installing and deploying the Omnilingual ASR Web Interface.

## Prerequisites

### Required
- **Docker** 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose** 2.0+ ([Install Compose](https://docs.docker.com/compose/install/))
- **8GB+ RAM** (16GB recommended)
- **20GB+ free disk space** (for models and data)

### Optional
- **NVIDIA GPU** with CUDA support (10-20x faster transcription)
- **NVIDIA Container Toolkit** (for GPU support in Docker)

## Installation Steps

### 1. Clone/Navigate to Repository

```bash
cd /root/omnilingual-asr
```

### 2. Download ASR Models

**Important**: Download models before starting Docker containers.

```bash
cd repo
python3 download_all_models.py
```

This downloads:
- **LLM models**: 300M, 1B, 3B, 7B parameter models (~10GB total)
- **CTC models**: Fast inference models (~5GB total)
- **Tokenizers**: Vocabulary files (~100MB)

Models are saved to: `~/.cache/fairseq2/assets/`

**Verify download**:
```bash
ls -lh ~/.cache/fairseq2/assets/
```

You should see multiple `.pt` files (model checkpoints).

### 3. Configure Environment (Optional)

```bash
cd ../web
cp .env.example .env
```

Edit `.env` to customize:
- Model selection (DEFAULT_MODEL)
- GPU/CPU usage (DEVICE)
- Upload limits (MAX_UPLOAD_SIZE)
- Database settings

### 4. Build and Start Services

#### Option A: Using Startup Script (Recommended)

```bash
./start.sh
```

The script will:
- Check dependencies
- Optionally download models
- Create environment file
- Build Docker images
- Start all services
- Show access URLs

#### Option B: Manual Docker Compose

```bash
docker-compose up --build -d
```

**Wait for services to start** (~30-60 seconds):
```bash
docker-compose logs -f
```

Press `Ctrl+C` when you see: "Application startup complete"

### 5. Verify Installation

#### Check Service Status
```bash
docker-compose ps
```

All services should show "Up" status:
- `omniasr_db` - PostgreSQL
- `omniasr_redis` - Redis
- `omniasr_web` - API Server
- `omniasr_worker` - Celery Worker
- `omniasr_frontend` - Web UI

#### Run Test Script
```bash
python3 test_pipeline.py
```

This automated test:
1. Generates test audio
2. Uploads to API
3. Starts transcription job
4. Monitors progress
5. Retrieves results
6. Tests all export formats

**Expected output**: "✅ ALL TESTS PASSED!"

#### Manual Browser Test

Open browser to: `http://localhost:3000`

You should see the Omnilingual ASR interface.

## GPU Support (Optional)

### Install NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Update Docker Compose for GPU

Edit `docker-compose.yml`:

```yaml
web:
  environment:
    - DEVICE=cuda  # Change from 'cpu' to 'cuda'
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]

worker:
  environment:
    - DEVICE=cuda  # Change from 'cpu' to 'cuda'
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Restart with GPU

```bash
docker-compose down
docker-compose up --build -d
```

### Verify GPU Usage

```bash
# Check GPU is visible
docker exec omniasr_worker nvidia-smi

# Monitor GPU during transcription
watch -n 1 nvidia-smi
```

## Troubleshooting

### Services Won't Start

**Check logs**:
```bash
docker-compose logs
```

**Common issues**:

1. **Port already in use**
   ```bash
   # Find process using port
   sudo lsof -i :8123
   sudo lsof -i :3000

   # Kill process or change port in docker-compose.yml
   ```

2. **Permission denied**
   ```bash
   sudo chmod +x start.sh test_pipeline.py
   ```

3. **Disk space full**
   ```bash
   df -h
   docker system prune -a  # Free up space
   ```

### Models Not Loading

**Check model cache**:
```bash
ls ~/.cache/fairseq2/assets/
```

**Re-download models**:
```bash
cd repo
rm -rf ~/.cache/fairseq2/assets/*
python3 download_all_models.py
```

**Check Docker volume mount**:
```bash
docker-compose exec worker ls /root/.cache/fairseq2/assets/
```

### Database Connection Failed

**Reset database**:
```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up --build -d
```

**Check PostgreSQL logs**:
```bash
docker-compose logs db
```

### Import Errors (fairseq2, omnilingual_asr)

**Check Python path in container**:
```bash
docker-compose exec worker python3 -c "import sys; print('\n'.join(sys.path))"
```

**Verify repo mount**:
```bash
docker-compose exec worker ls -la /app/repo/src/
```

**Rebuild containers**:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Out of Memory

**Reduce Celery workers**:

Edit `docker-compose.yml`:
```yaml
worker:
  command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1
```

**Use smaller model**:
- Change `DEFAULT_MODEL` in `.env` to `CTC_1B` or `LLM_1B`

**Increase Docker memory limit**:
```bash
# Docker Desktop: Settings > Resources > Memory (set to 8GB+)
```

### Transcription Fails

**Check worker logs**:
```bash
docker-compose logs worker
```

**Common issues**:
- Audio file corrupted → Try different file
- Model not loaded → Check model cache
- GPU out of memory → Switch to CPU or smaller model

**Manual test**:
```bash
docker-compose exec worker python3 -c "
from app.services.asr_service import ASRService
asr = ASRService(model_name='CTC_1B', device='cpu')
print('ASR service loaded successfully')
"
```

## Upgrading

### Update Code

```bash
cd /root/omnilingual-asr
git pull  # If using git
```

### Rebuild Containers

```bash
cd web
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Update Models

```bash
cd repo
python3 download_all_models.py
```

## Uninstallation

### Stop and Remove Containers

```bash
cd /root/omnilingual-asr/web
docker-compose down
```

### Remove Volumes (Data)

```bash
docker-compose down -v  # WARNING: Deletes database and storage
```

### Remove Images

```bash
docker-compose down --rmi all
```

### Remove Models

```bash
rm -rf ~/.cache/fairseq2/
```

## Production Deployment

### Security

1. **Change default passwords** in `.env`:
   ```
   POSTGRES_PASSWORD=<strong-password>
   SECRET_KEY=<random-secret-key>
   ```

2. **Enable HTTPS** with Nginx reverse proxy

3. **Set up firewall**:
   ```bash
   sudo ufw allow 3000/tcp  # Frontend
   sudo ufw allow 8123/tcp  # API (optional, if accessed directly)
   ```

4. **Disable debug mode**:
   ```
   DEBUG=false
   ```

### Scaling

**Multiple workers**:
```bash
docker-compose up --scale worker=4 -d
```

**Use PostgreSQL externally**:
- Set DATABASE_URL to external PostgreSQL server
- Remove `db` service from docker-compose.yml

**Load balancing**:
- Deploy multiple instances behind Nginx/HAProxy
- Use shared PostgreSQL and Redis

### Monitoring

**Prometheus + Grafana** (optional):

Add to `docker-compose.yml`:
```yaml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana
  ports:
    - "3001:3000"
  depends_on:
    - prometheus
```

**Health checks**:
```bash
# API health
curl http://localhost:8123/health

# Database health
docker-compose exec db pg_isready
```

### Backup

**Database backup**:
```bash
docker-compose exec db pg_dump -U omniasr omniasr > backup.sql
```

**Restore**:
```bash
docker-compose exec -T db psql -U omniasr omniasr < backup.sql
```

**Storage backup**:
```bash
docker run --rm -v omniasr_storage_data:/data -v $(pwd):/backup \
  ubuntu tar czf /backup/storage_backup.tar.gz /data
```

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Run test: `python3 test_pipeline.py`
- Review documentation: `README.md`

---

**Next**: See [QUICKSTART.md](QUICKSTART.md) for usage guide
