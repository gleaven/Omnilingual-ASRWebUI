# Omnilingual ASR - Web Transcription Platform

A powerful web-based multilingual automatic speech recognition (ASR) platform with translation capabilities, supporting 1600+ languages powered by Meta's Seamless M4T model.

![Dark Mode UI](https://img.shields.io/badge/UI-Dark%20Mode-blueviolet)
![GPU Accelerated](https://img.shields.io/badge/GPU-CUDA%20Enabled-green)
![Languages](https://img.shields.io/badge/Languages-1600%2B-blue)

## Features

### 🎙️ Speech Recognition
- **1600+ Language Support** - Powered by Meta's Omnilingual ASR (Seamless M4T)
- **Smart Audio Chunking** - Voice Activity Detection (VAD) for optimal segmentation
- **Multiple Models** - Choose between CTC_1B (fast) and LLM_7B (accurate)
- **Batch Processing** - Process multiple audio chunks simultaneously for 2-4x speedup
- **GPU Acceleration** - CUDA support for 10-20x faster transcription

### 🌐 Translation
- **200+ Target Languages** - Powered by Facebook's NLLB-200 model
- **Automatic Language Detection** - Detects source language using langdetect + character analysis
- **Batch Translation** - Efficient parallel translation of segments
- **Segment-Level Translation** - Each transcription segment includes translation

### 🎭 Speaker Diarization
- **Speaker Identification** - Automatically identify different speakers
- **Speaker Statistics** - Track speaking time and segment count per speaker
- **Custom Speaker Names** - Label speakers with custom names

### 📁 Input Sources
- **File Upload** - Support for MP3, WAV, M4A, OGG, FLAC
- **YouTube Integration** - Direct download and transcription from YouTube URLs
- **Drag & Drop** - Easy file upload interface

### 📤 Export Formats
- **TXT** - Plain text with speaker labels
- **JSON** - Complete structured data
- **SRT** - SubRip subtitles for video
- **VTT** - WebVTT subtitles
- **CSV** - Spreadsheet format with timestamps

### 🎨 User Interface
- **Dark Mode** - Modern, easy-on-the-eyes dark theme
- **Real-time Progress** - Live updates on transcription progress
- **Job History** - View and manage all transcription jobs
- **Delete Jobs** - Clean up old transcriptions with confirmation

## Architecture

```
┌─────────────────┐
│  Nginx Frontend │ ← Dark Mode UI
│   (Port 8123)   │
└────────┬────────┘
         │
┌────────▼────────┐
│  FastAPI Web    │ ← REST API
│   (Port 8123)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────┐
│ Redis │ │PostgreSQL│
└───┬───┘ └──┬──────┘
    │        │
┌───▼────────▼───┐
│  Celery Worker │ ← GPU Processing
│  (2 concurrent) │
└────────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- NVIDIA GPU with CUDA support (optional, will fall back to CPU)
- 16GB+ RAM recommended
- 50GB+ disk space for models

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd omnilingual-asr/web
```

2. **Start the services**
```bash
docker-compose up -d
```

3. **Wait for models to download** (first time only, ~10-15 minutes)
```bash
docker-compose logs -f worker
```

4. **Access the web interface**
```
http://localhost:8123
```

### Configuration

The application uses environment variables for configuration:

```bash
# Database
DATABASE_URL=postgresql://omniasr:omniasr@db:5432/omniasr

# Redis
REDIS_URL=redis://redis:6379/0

# Storage
STORAGE_PATH=/app/storage

# Processing
DEVICE=cuda                    # Use 'cpu' if no GPU
DEFAULT_MODEL=CTC_1B          # or 'LLM_7B' for higher accuracy
MODEL_CACHE_DIR=/root/.cache/fairseq2

# Worker Settings
CELERY_CONCURRENCY=2          # Number of parallel workers
WORKER_MAX_TASKS_PER_CHILD=100  # Tasks before worker restart
TASK_TIME_LIMIT=7200          # 2 hours timeout
```

## Usage

### Web Interface

1. **Upload Audio**
   - Click "Choose File" or drag & drop audio files
   - Or paste a YouTube URL in the YouTube section

2. **Configure Settings**
   - **Model**: CTC_1B (fast) or LLM_7B (accurate)
   - **Language Hint**: Optional source language (auto-detected if not specified)
   - **Translation**: Enable/disable translation
   - **Target Language**: Select translation language (default: English)
   - **Speaker Diarization**: Enable to identify multiple speakers
   - **Chunk Duration**: Audio chunk size (10-40 seconds)

3. **Start Transcription**
   - Click "Start Transcription"
   - Monitor real-time progress
   - View results when complete

4. **Export Results**
   - Choose export format (TXT, JSON, SRT, VTT, CSV)
   - Download the file

5. **Manage Jobs**
   - View all jobs in history
   - Delete completed jobs with 🗑️ button

### API Endpoints

#### Upload Audio
```bash
POST /api/upload
Content-Type: multipart/form-data

curl -X POST -F "file=@audio.mp3" http://localhost:8123/api/upload
```

#### Download YouTube Audio
```bash
POST /api/youtube
Content-Type: application/json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID"
}
```

#### Create Transcription Job
```bash
POST /api/transcribe
Content-Type: application/json
{
  "audio_id": 1,
  "model": "CTC_1B",
  "language_hint": null,
  "enable_diarization": false,
  "enable_translation": true,
  "target_language": "eng",
  "chunk_duration": 30
}
```

#### Get Job Status
```bash
GET /api/jobs/{job_id}

Response:
{
  "job_id": 1,
  "status": "completed",
  "progress": 100.0,
  "current_step": "Completed",
  "error_message": null
}
```

#### Get Transcription Result
```bash
GET /api/jobs/{job_id}/result

Response:
{
  "job_id": 1,
  "status": "completed",
  "full_text": "Original transcription...",
  "full_translated_text": "Translated text...",
  "detected_languages": [
    {
      "code": "zho",
      "name": "Chinese",
      "confidence": 0.95
    }
  ],
  "speakers": [...],
  "segments": [
    {
      "start_time": 0.0,
      "end_time": 5.2,
      "text": "Original text",
      "translated_text": "Translated text",
      "speaker_label": "SPEAKER_00"
    }
  ]
}
```

#### List Jobs
```bash
GET /api/jobs?status=completed&limit=10

Response:
{
  "items": [...],
  "total": 50,
  "page": 1,
  "page_size": 10
}
```

#### Delete Job
```bash
DELETE /api/jobs/{job_id}

Response:
{
  "message": "Job 1 deleted successfully"
}
```

#### Export Transcription
```bash
GET /api/jobs/{job_id}/export?format=srt

# Formats: txt, json, srt, vtt, csv
```

## Supported Languages

### ASR (Speech Recognition)
1600+ languages supported by Omnilingual ASR including:
- English, Spanish, French, German, Italian, Portuguese
- Chinese (Mandarin, Cantonese), Japanese, Korean
- Arabic, Hindi, Russian, Turkish, Vietnamese
- And 1590+ more languages

### Translation
200+ languages supported by NLLB-200 including:
- Major European languages (English, Spanish, French, German, etc.)
- Asian languages (Chinese, Japanese, Korean, Vietnamese, Thai, etc.)
- Middle Eastern languages (Arabic, Hebrew, Persian, Turkish)
- Indian languages (Hindi, Bengali, Tamil, Telugu, etc.)
- African languages (Swahili, Afrikaans, etc.)

## Performance

### Processing Speed (with GPU)
- **Audio Processing**: ~2-3x real-time (10 min audio = 3-5 min processing)
- **Batch Mode**: 2-4x faster than sequential processing
- **GPU Speedup**: 10-20x faster than CPU

### Example Times (39.3s YouTube video on NVIDIA RTX 6000)
- **Total Processing**: ~17 seconds
  - Audio loading: 2s
  - Transcription (Chinese): 8s
  - Language detection: <1s
  - Translation to English: 6s

### Resource Requirements
- **CPU**: 4+ cores recommended
- **RAM**: 16GB minimum, 32GB recommended
- **GPU**: NVIDIA GPU with 8GB+ VRAM (optional)
- **Disk**: 50GB for models + storage for audio files

## Docker Services

### Services Overview
- **db** (PostgreSQL): Database for jobs, segments, speakers
- **redis**: Message broker for Celery
- **web** (FastAPI): REST API server
- **worker** (Celery): Background processing with GPU
- **frontend** (Nginx): Static file server for UI

### Service Management

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f worker
docker-compose logs -f web

# Restart specific service
docker-compose restart worker

# Check service status
docker-compose ps

# Access database
docker-compose exec db psql -U omniasr -d omniasr

# Access worker shell
docker-compose exec worker bash
```

## Database Schema

### Processing Jobs
- Job metadata, status, progress
- Model configuration
- Translation settings

### Audio Files
- File metadata, duration
- Source type (upload/youtube)

### Transcription Segments
- Start/end timestamps
- Original and translated text
- Speaker assignment

### Speakers
- Speaker labels and statistics
- Total speaking time
- Number of segments

### Detected Languages
- Language codes and names
- Confidence scores

### Translations
- Full translated text
- Source/target languages
- Translation model used

## Development

### Project Structure
```
web/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   ├── models.py      # Database models
│   │   ├── schemas.py     # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   │   ├── asr_service.py
│   │   │   ├── translation_service.py
│   │   │   ├── language_detector.py
│   │   │   └── ...
│   │   ├── tasks/         # Celery tasks
│   │   └── core/          # Configuration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── index.html         # Dark mode UI
│   ├── Dockerfile
│   └── nginx.conf
└── docker-compose.yml
```

### Adding New Languages to Translation UI

Edit `frontend/index.html` and add options to the `targetLanguage` select:

```html
<option value="fra">French</option>
<option value="deu">German</option>
<!-- Add more languages -->
```

See `language_detector.py` for ISO 639-3 language codes.

## Troubleshooting

### Models not downloading
```bash
# Check worker logs
docker-compose logs -f worker

# Manually trigger download
docker-compose exec worker python -c "from fairseq2.models import load_model; load_model('seamless_m4t_v2_medium')"
```

### GPU not detected
```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Verify worker sees GPU
docker-compose exec worker python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

### Worker timeout/crash
```bash
# Increase timeout in docker-compose.yml
environment:
  - TASK_TIME_LIMIT=14400  # 4 hours

# Or reduce chunk duration in UI settings
```

### Out of memory
```bash
# Reduce worker concurrency
docker-compose.yml:
  command: celery -A app.tasks.celery_app worker --concurrency=1

# Or use smaller model
DEFAULT_MODEL=CTC_1B  # Instead of LLM_7B
```

### Database issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d

# Or manually fix
docker-compose exec db psql -U omniasr -d omniasr
```

## Technology Stack

- **Backend**: FastAPI, Python 3.10+
- **Task Queue**: Celery + Redis
- **Database**: PostgreSQL 15
- **Frontend**: Vanilla JavaScript, Modern CSS
- **Web Server**: Nginx
- **ML Models**:
  - Omnilingual ASR (Meta Seamless M4T)
  - NLLB-200-distilled-600M (Facebook)
  - Silero VAD
  - langdetect
- **Audio Processing**: FFmpeg, librosa, soundfile
- **Containerization**: Docker, Docker Compose

## License

See the main repository for license information.

## Credits

- **Meta AI** - Seamless M4T (Omnilingual ASR)
- **Facebook AI** - NLLB-200 Translation Model
- **Silero Team** - Voice Activity Detection
- **yt-dlp** - YouTube audio extraction

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review Docker logs: `docker-compose logs -f`
3. Open an issue on the repository

---

**Built with ❤️ using cutting-edge AI models for multilingual speech recognition and translation**
