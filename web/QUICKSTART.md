# Quick Start Guide

Get the Omnilingual ASR Web Interface running in 3 simple steps!

## Step 1: Download Models (One-Time Setup)

```bash
cd /root/omnilingual-asr/repo
python download_all_models.py
```

This downloads the AI models (~5-10GB). It only needs to be done once.

## Step 2: Start the Application

```bash
cd /root/omnilingual-asr/web
./start.sh
```

Or manually with Docker Compose:

```bash
docker-compose up --build
```

## Step 3: Open in Browser

Navigate to:
```
http://localhost:3000
```

That's it! You're ready to transcribe audio.

---

## Quick Test

Run the automated test to verify everything works:

```bash
cd /root/omnilingual-asr/web
python test_pipeline.py
```

This will:
- Generate test audio
- Upload it
- Transcribe it
- Show results
- Test exports

---

## Common Commands

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f
```

### Restart Services
```bash
docker-compose restart
```

### Check Status
```bash
docker-compose ps
```

---

## Troubleshooting

### Services won't start
```bash
# Check if ports are in use
sudo lsof -i :3000
sudo lsof -i :8123

# Or change ports in docker-compose.yml
```

### Models not found
```bash
# Verify models are downloaded
ls ~/.cache/fairseq2/assets/

# Re-download if needed
cd ../repo
python download_all_models.py
```

### Database issues
```bash
# Reset database
docker-compose down -v
docker-compose up --build
```

---

## What's Running?

| Service    | Port | Description           |
|------------|------|-----------------------|
| Frontend   | 3000 | Web UI                |
| Backend    | 8123 | API Server            |
| PostgreSQL | 5432 | Database              |
| Redis      | 6379 | Task Queue            |

---

## Next Steps

1. **Upload Audio** - Drag and drop any audio file
2. **Try YouTube** - Paste a YouTube URL
3. **Adjust Settings** - Choose different models
4. **Export Results** - Download in various formats

Enjoy transcribing! 🎤
