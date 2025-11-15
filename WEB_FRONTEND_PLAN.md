# Omnilingual ASR Web Frontend - Comprehensive Implementation Plan

## Executive Summary

This document outlines the complete implementation plan for a web-based interface to the Omnilingual ASR system. The frontend will provide a user-friendly way to upload audio files, extract audio from YouTube videos, process them through an intelligent chunking pipeline, transcribe them using the existing ASR models, identify speakers, detect languages, and persist all results in a database.

---

## 1. Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web Browser                              │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Upload UI     │  │  YouTube UI  │  │  Transcription UI  │  │
│  └────────────────┘  └──────────────┘  └────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Web Server (Port 8123)               │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ REST API   │  │  WebSocket   │  │  Static File Server   │  │
│  │ Endpoints  │  │  (Progress)  │  │  (Frontend Assets)    │  │
│  └────────────┘  └──────────────┘  └────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Processing Pipeline Layer                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ Audio Processor │→ │  Smart Chunker   │→ │  VAD Engine   │  │
│  │ (Format Conv.)  │  │ (Word Boundary)  │  │ (Silero VAD)  │  │
│  └─────────────────┘  └──────────────────┘  └───────────────┘  │
│                                                                  │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ ASR Inference   │  │   Speaker        │  │  Language     │  │
│  │ (Omni Models)   │  │   Diarization    │  │  Detection    │  │
│  │                 │  │   (pyannote)     │  │  (Built-in)   │  │
│  └─────────────────┘  └──────────────────┘  └───────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           YouTube Downloader (yt-dlp)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer (PostgreSQL)                   │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  Audio     │  │ Transcription│  │  Processing Jobs       │  │
│  │  Files     │  │  Segments    │  │  (Status/Progress)     │  │
│  └────────────┘  └──────────────┘  └────────────────────────┘  │
│                                                                  │
│  ┌────────────┐  ┌──────────────┐                              │
│  │  Speakers  │  │  Languages   │                              │
│  └────────────┘  └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Storage Layer (File System)                   │
│  ┌─────────────────┐  ┌──────────────────┐                     │
│  │  Original Audio │  │  Processed Audio │                     │
│  │  Files          │  │  Chunks          │                     │
│  └─────────────────┘  └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

#### Backend
- **Web Framework**: FastAPI (async, high performance, auto-docs)
- **Database**: PostgreSQL (production) / SQLite (development)
- **ORM**: SQLAlchemy with Alembic migrations
- **Task Queue**: Celery with Redis (for background processing)
- **WebSocket**: FastAPI WebSocket for real-time progress updates

#### Audio Processing
- **Format Conversion**: FFmpeg (via pydub or ffmpeg-python)
- **Voice Activity Detection**: Silero VAD (lightweight, accurate)
- **Speaker Diarization**: pyannote.audio (pre-trained models)
- **YouTube Extraction**: yt-dlp (robust, actively maintained)
- **ASR**: Existing Omnilingual ASR models (300M, 1B, 3B, 7B)

#### Frontend
- **Framework**: React with TypeScript (or Vue.js alternative)
- **UI Components**: Material-UI or Ant Design
- **State Management**: React Query for server state
- **File Upload**: react-dropzone with chunked upload support
- **Audio Visualization**: WaveSurfer.js
- **Real-time Updates**: WebSocket client

#### DevOps
- **Containerization**: Docker + Docker Compose
- **Reverse Proxy**: Nginx (optional, for production)
- **Monitoring**: Prometheus + Grafana (optional)

---

## 2. Database Schema

### 2.1 Entity Relationship Diagram

```
┌─────────────────────────┐
│     audio_files         │
├─────────────────────────┤
│ id (PK)                 │
│ filename                │
│ original_filename       │
│ file_path               │
│ file_size               │
│ duration_seconds        │
│ sample_rate             │
│ channels                │
│ format                  │
│ source_type             │  (upload, youtube, url)
│ source_url              │  (for youtube/url)
│ upload_date             │
│ checksum (SHA256)       │
└──────────┬──────────────┘
           │
           │ 1:N
           ▼
┌─────────────────────────┐
│   processing_jobs       │
├─────────────────────────┤
│ id (PK)                 │
│ audio_file_id (FK)      │
│ status                  │  (queued, processing, completed, failed)
│ model_name              │  (CTC_1B, LLM_7B, etc.)
│ language_hint           │  (optional)
│ enable_diarization      │
│ chunk_duration          │
│ progress_percent        │
│ current_step            │
│ error_message           │
│ created_at              │
│ started_at              │
│ completed_at            │
└──────────┬──────────────┘
           │
           │ 1:N
           ▼
┌─────────────────────────┐
│  transcription_segments │
├─────────────────────────┤
│ id (PK)                 │
│ job_id (FK)             │
│ chunk_index             │
│ start_time              │  (seconds)
│ end_time                │  (seconds)
│ text                    │
│ confidence              │  (optional)
│ speaker_id (FK)         │  (optional)
│ chunk_file_path         │
└──────────┬──────────────┘
           │
           │ N:1
           ▼
┌─────────────────────────┐
│       speakers          │
├─────────────────────────┤
│ id (PK)                 │
│ job_id (FK)             │
│ speaker_label           │  (SPEAKER_00, SPEAKER_01, etc.)
│ total_speaking_time     │
│ num_segments            │
└─────────────────────────┘

┌─────────────────────────┐
│   detected_languages    │
├─────────────────────────┤
│ id (PK)                 │
│ job_id (FK)             │
│ language_code           │  (ISO 639-3)
│ language_name           │
│ confidence              │
│ time_percentage         │  (% of audio in this language)
└─────────────────────────┘
```

### 2.2 Table Definitions (SQLAlchemy Models)

**audio_files**
- Stores metadata about uploaded/downloaded audio files
- Tracks source (upload, YouTube, URL)
- Includes checksum for deduplication

**processing_jobs**
- One job per transcription request
- Tracks progress and status in real-time
- Stores configuration (model, language hint, diarization settings)

**transcription_segments**
- Individual transcribed chunks
- Linked to speakers (if diarization enabled)
- Preserves timing information for reassembly

**speakers**
- Speaker profiles identified by diarization
- Statistics on speaking time and segment count

**detected_languages**
- Languages detected in the audio
- Confidence scores and time percentages
- Supports multilingual audio

---

## 3. API Endpoints Design

### 3.1 Audio Upload & Management

#### `POST /api/upload`
Upload audio file for transcription
- **Request**: `multipart/form-data` with audio file
- **Response**: `{ audio_id: string, filename: string, duration: number }`
- **Supported Formats**: WAV, MP3, M4A, FLAC, OGG, WEBM, MP4, etc.

#### `POST /api/youtube`
Extract audio from YouTube video
- **Request**: `{ url: string }`
- **Response**: `{ audio_id: string, title: string, duration: number }`
- **Validation**: YouTube URL validation, age-restricted check

#### `GET /api/audio/{audio_id}`
Get audio file metadata
- **Response**: Audio file details, waveform data (optional)

#### `DELETE /api/audio/{audio_id}`
Delete audio file and associated data
- **Cascade**: Deletes jobs, transcriptions, speakers

### 3.2 Transcription Processing

#### `POST /api/transcribe`
Start transcription job
- **Request**:
  ```json
  {
    "audio_id": "string",
    "model": "LLM_7B" | "LLM_3B" | "LLM_1B" | "CTC_1B",
    "language_hint": "eng" | null,
    "enable_diarization": true,
    "chunk_duration": 30
  }
  ```
- **Response**: `{ job_id: string, status: "queued" }`

#### `GET /api/jobs/{job_id}`
Get job status and progress
- **Response**:
  ```json
  {
    "job_id": "string",
    "status": "processing",
    "progress": 45,
    "current_step": "Transcribing chunk 3/10",
    "created_at": "timestamp"
  }
  ```

#### `GET /api/jobs/{job_id}/result`
Get completed transcription
- **Response**:
  ```json
  {
    "job_id": "string",
    "full_text": "string",
    "detected_languages": [
      { "code": "eng", "name": "English", "confidence": 0.95 }
    ],
    "speakers": [
      {
        "id": "SPEAKER_00",
        "speaking_time": 120.5,
        "segments": 15
      }
    ],
    "segments": [
      {
        "start": 0.0,
        "end": 28.3,
        "text": "string",
        "speaker": "SPEAKER_00"
      }
    ]
  }
  ```

#### `GET /api/jobs/{job_id}/export`
Export transcription in various formats
- **Query Params**: `format=txt|json|srt|vtt|word`
- **Response**: Formatted transcription file

### 3.3 History & Search

#### `GET /api/jobs`
List all transcription jobs
- **Query Params**: `status`, `limit`, `offset`, `sort`
- **Response**: Paginated list of jobs with metadata

#### `GET /api/search`
Search transcriptions by text
- **Query Params**: `query`, `language`, `speaker`
- **Response**: Matching segments with context

### 3.4 WebSocket

#### `WS /ws/jobs/{job_id}`
Real-time job progress updates
- **Messages**:
  ```json
  {
    "type": "progress",
    "job_id": "string",
    "progress": 67,
    "step": "Transcribing chunk 7/10"
  }
  ```

---

## 4. Audio Processing Pipeline Details

### 4.1 Smart Chunking Algorithm

**Objective**: Split audio into ~30-second chunks without cutting mid-word

**Algorithm**:
1. **Voice Activity Detection (VAD)**
   - Use Silero VAD to detect speech segments
   - Identify silence/pause boundaries

2. **Chunk Planning**
   - Target chunk duration: 30 seconds (configurable)
   - Tolerance window: 25-35 seconds
   - Find optimal split points (pauses) within tolerance

3. **Word Boundary Detection**
   - For each potential split point:
     - Check if it falls in a silence period (>200ms)
     - Verify no energy spike (indicating mid-word)

4. **Fallback Strategy**
   - If no good pause found within tolerance:
     - Extend to next pause (max 40 seconds, ASR model limit)
     - If still no pause, use VAD energy minimum

5. **Overlap Strategy**
   - Add 0.5-second overlap between chunks
   - Helps with context preservation
   - Remove duplicate text in post-processing

**Implementation Pseudocode**:
```python
def smart_chunk_audio(audio, target_duration=30, tolerance=5):
    # Get VAD speech segments
    vad_segments = detect_speech_segments(audio)

    chunks = []
    current_start = 0

    while current_start < len(audio):
        # Calculate ideal end point
        ideal_end = current_start + target_duration
        min_end = current_start + (target_duration - tolerance)
        max_end = current_start + (target_duration + tolerance)

        # Find best pause within tolerance window
        best_pause = find_best_pause(
            vad_segments,
            start=min_end,
            end=max_end,
            ideal=ideal_end
        )

        if best_pause:
            chunk_end = best_pause
        else:
            # Fallback: extend to next pause or max limit
            chunk_end = find_next_pause(vad_segments, ideal_end, max_limit=40)

        # Extract chunk with overlap
        overlap = 0.5
        chunk = audio[current_start : chunk_end + overlap]
        chunks.append({
            'audio': chunk,
            'start_time': current_start,
            'end_time': chunk_end
        })

        current_start = chunk_end

    return chunks
```

### 4.2 Processing Workflow

```
Audio File
    ↓
┌──────────────────────────────────────┐
│ 1. Format Validation & Conversion    │
│    - Detect format (FFmpeg)          │
│    - Convert to WAV 16kHz mono       │
│    - Validate duration (<10 hours)   │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│ 2. Voice Activity Detection (VAD)    │
│    - Run Silero VAD                  │
│    - Identify speech segments        │
│    - Calculate silence boundaries    │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│ 3. Smart Chunking                    │
│    - Apply algorithm (see 4.1)       │
│    - Save chunks to temp files       │
│    - Record chunk metadata           │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│ 4. Speaker Diarization (Optional)    │
│    - Run pyannote.audio on full file │
│    - Extract speaker timeline        │
│    - Map speakers to chunks          │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│ 5. Parallel ASR Processing           │
│    - Batch chunks (e.g., 4 at a time)│
│    - Run ASR inference on each chunk │
│    - Extract language probabilities  │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│ 6. Post-Processing                   │
│    - Merge chunk transcriptions      │
│    - Remove overlap duplicates       │
│    - Align speaker labels            │
│    - Aggregate language detection    │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│ 7. Database Persistence              │
│    - Save segments to DB             │
│    - Create speaker records          │
│    - Update job status               │
└──────────────────────────────────────┘
    ↓
Final Transcription
```

### 4.3 Language Detection Strategy

The Omnilingual ASR system has built-in language detection capabilities. We'll use a hybrid approach:

1. **Per-Chunk Detection**
   - Extract language probabilities from each chunk's ASR output
   - LLM models output token probabilities that can indicate language

2. **Aggregation**
   - Count language occurrences across all chunks
   - Weight by chunk duration
   - Calculate confidence scores

3. **Multi-Language Handling**
   - Detect code-switching (multiple languages in one audio)
   - Report all languages with >10% time presence

---

## 5. Frontend UI Design

### 5.1 Page Structure

#### **Home/Upload Page** (`/`)
- Drag-and-drop upload zone
- File browser button
- YouTube URL input field
- List of supported formats
- Recently uploaded files (last 10)

#### **Processing Dashboard** (`/jobs`)
- Active jobs with real-time progress bars
- Job history table (sortable, filterable)
- Quick actions (view, download, delete)

#### **Transcription Viewer** (`/transcription/{job_id}`)
- Full text display
- Timestamp navigation
- Speaker-colored text segments
- Audio player with sync (click segment → jump to time)
- Waveform visualization with segment highlights
- Export buttons (TXT, JSON, SRT, VTT, DOCX)

#### **Settings Page** (`/settings`)
- Default model selection
- Default chunk duration
- Enable/disable diarization by default
- Language preferences
- API key management (future feature)

### 5.2 UI Components

#### Upload Component
```
┌──────────────────────────────────────────────────────────┐
│  📁 Drag & Drop Audio File Here                          │
│                                                           │
│  or                                                       │
│                                                           │
│  [Browse Files]                                           │
│                                                           │
│  ─────────────────── OR ────────────────────              │
│                                                           │
│  🎬 YouTube URL:                                          │
│  [https://youtube.com/watch?v=_______________]  [Extract]│
│                                                           │
│  Supported: MP3, WAV, M4A, FLAC, OGG, MP4, WEBM          │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Transcription Settings                                   │
│                                                           │
│  Model:        [LLM 7B (Best Quality) ▼]                 │
│  Language:     [Auto-detect ▼]                           │
│  Diarization:  [✓] Identify Speakers                     │
│                                                           │
│                              [Start Transcription]        │
└──────────────────────────────────────────────────────────┘
```

#### Progress Component
```
┌──────────────────────────────────────────────────────────┐
│  🎵 my_audio.mp3 (5:23)                                   │
│                                                           │
│  Status: Processing                                       │
│  Progress: ████████████░░░░░░░░░░░ 67%                   │
│                                                           │
│  Current Step: Transcribing chunk 7/10                    │
│  Elapsed: 2m 34s                                          │
│                                                           │
│                                       [Cancel] [Details]  │
└──────────────────────────────────────────────────────────┘
```

#### Transcription Viewer Component
```
┌──────────────────────────────────────────────────────────┐
│  my_audio.mp3 - English (95% confidence)                  │
│  Duration: 5:23 | 2 Speakers | Model: LLM 7B              │
│                                                           │
│  [Export ▼] [Share] [Delete]                             │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Waveform [████▌░░▌████▌░░░░▌███▌░░] 🔊 ─────○─────     │
│                                      0:00 / 5:23          │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Transcription                                            │
│                                                           │
│  [00:00 - 00:28] SPEAKER_00                              │
│  Hello everyone, welcome to today's presentation. We're  │
│  going to discuss the latest developments in artificial  │
│  intelligence and machine learning.                       │
│                                                           │
│  [00:28 - 00:52] SPEAKER_01                              │
│  Thank you for having me. I'm excited to share our       │
│  research findings with the audience today.               │
│                                                           │
│  [00:52 - 01:15] SPEAKER_00                              │
│  Let's start with the background...                      │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## 6. Additional Feature Improvements

### 6.1 Core Enhancements

1. **Multi-File Batch Upload**
   - Upload and process multiple files simultaneously
   - Queue management with priority settings
   - Bulk export functionality

2. **Advanced Language Support**
   - Language auto-detection with confidence scores
   - Manual language override option
   - Code-switching detection and labeling

3. **Speaker Management**
   - Custom speaker naming (rename SPEAKER_00 → "John Doe")
   - Speaker profile persistence across jobs
   - Voice print matching for speaker recognition

4. **Quality Options**
   - Model selection (Fast: CTC_1B, Balanced: LLM_1B, Best: LLM_7B)
   - Quality vs. Speed trade-off indicators
   - Estimated processing time display

5. **Transcription Editing**
   - In-browser editor for manual corrections
   - Version history (original vs. edited)
   - Collaborative editing (future)

### 6.2 Advanced Features

6. **Audio Preprocessing**
   - Noise reduction (noisereduce library)
   - Volume normalization
   - Speed adjustment (playback rate)

7. **Vocabulary Customization**
   - Custom word lists (medical terms, names, jargon)
   - Context hints for domain-specific transcription
   - Acronym expansion

8. **Export Formats**
   - Plain text (TXT)
   - JSON (structured data)
   - Subtitles (SRT, VTT, ASS)
   - Document (DOCX, PDF)
   - Timestamped (TSV, CSV)

9. **Integration Capabilities**
   - REST API with authentication (API keys)
   - Webhook notifications on job completion
   - Cloud storage integration (S3, Google Drive, Dropbox)

10. **Search & Analytics**
    - Full-text search across all transcriptions
    - Keyword highlighting and extraction
    - Speaking time analytics per speaker
    - Language distribution charts

### 6.3 User Experience

11. **Real-Time Feedback**
    - Live progress updates via WebSocket
    - Estimated time remaining
    - Error recovery and retry mechanisms

12. **Accessibility**
    - Keyboard shortcuts for navigation
    - Screen reader support
    - High-contrast mode

13. **Mobile Responsiveness**
    - Touch-friendly interface
    - Responsive layouts
    - Mobile upload support

### 6.4 Performance Optimizations

14. **Caching & Deduplication**
    - SHA-256 checksum to detect duplicate files
    - Reuse transcriptions for identical files
    - Model caching (keep models in memory)

15. **Scalability**
    - Celery task queue for background processing
    - Horizontal scaling with multiple workers
    - GPU pooling for concurrent inference

16. **Streaming Processing**
    - Stream large files instead of loading entirely
    - Progressive transcription display (show chunks as they complete)
    - Chunked file upload for large files

### 6.5 Security & Privacy

17. **Authentication & Authorization**
    - User accounts with login/logout
    - Role-based access (admin, user, guest)
    - Private vs. public transcriptions

18. **Data Privacy**
    - Optional encryption at rest (database encryption)
    - Automatic deletion after N days (configurable)
    - GDPR compliance features (data export, deletion requests)

19. **Rate Limiting**
    - API rate limiting (per user/IP)
    - Upload size limits (e.g., 500MB per file)
    - Concurrent job limits

---

## 7. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Set up project structure (backend + frontend)
- [ ] Create database schema and migrations
- [ ] Implement basic FastAPI server with CORS
- [ ] Build audio upload endpoint
- [ ] Create simple file storage system
- [ ] Set up development environment (Docker Compose)

### Phase 2: Core Pipeline (Week 3-4)
- [ ] Implement FFmpeg audio format conversion
- [ ] Integrate Silero VAD for speech detection
- [ ] Build smart chunking algorithm
- [ ] Connect to Omnilingual ASR inference pipeline
- [ ] Implement basic transcription job processing
- [ ] Add job status tracking and persistence

### Phase 3: Advanced Features (Week 5-6)
- [ ] Integrate pyannote.audio for speaker diarization
- [ ] Implement speaker-to-segment mapping
- [ ] Add language detection and aggregation
- [ ] Build YouTube audio extraction (yt-dlp)
- [ ] Implement chunk overlap removal
- [ ] Add transcription reassembly logic

### Phase 4: Frontend (Week 7-8)
- [ ] Create React app structure
- [ ] Build upload UI component
- [ ] Implement job dashboard with real-time updates
- [ ] Create transcription viewer with audio sync
- [ ] Add waveform visualization
- [ ] Implement export functionality

### Phase 5: Enhancements (Week 9-10)
- [ ] Add WebSocket support for real-time progress
- [ ] Implement Celery task queue
- [ ] Add batch upload support
- [ ] Build search functionality
- [ ] Create user settings page
- [ ] Add multiple export formats

### Phase 6: Polish & Deploy (Week 11-12)
- [ ] Write comprehensive tests (unit + integration)
- [ ] Create deployment documentation
- [ ] Set up production configuration (Nginx, HTTPS)
- [ ] Implement rate limiting and security features
- [ ] Add monitoring and logging
- [ ] Create user documentation

---

## 8. Technical Specifications

### 8.1 File Format Support

**Input Formats** (via FFmpeg):
- Audio: MP3, WAV, FLAC, OGG, M4A, AAC, WMA, AIFF
- Video: MP4, MKV, AVI, MOV, WEBM, FLV (extract audio)
- Streaming: HLS, DASH (future)

**Processing Format**:
- Internal: WAV, 16kHz, mono, 16-bit PCM

**Export Formats**:
- Text: TXT, JSON, CSV, TSV
- Subtitles: SRT, VTT, ASS
- Documents: DOCX, PDF
- Data: JSON with full metadata

### 8.2 Performance Targets

- **Upload Speed**: Limited by network (100 MB/s target)
- **Chunk Processing**: 1-2x real-time (30s audio in 15-60s)
- **Speaker Diarization**: 0.5x real-time (30s audio in 15s)
- **Database Query**: <100ms for most queries
- **WebSocket Latency**: <50ms for progress updates
- **Concurrent Jobs**: 10+ jobs with 4-GPU system

### 8.3 Resource Requirements

**Development**:
- CPU: 4+ cores
- RAM: 16GB+
- GPU: Optional (CPU inference supported)
- Storage: 10GB+ for models

**Production (Recommended)**:
- CPU: 16+ cores
- RAM: 64GB+
- GPU: NVIDIA with 16GB+ VRAM (e.g., V100, A100)
- Storage: 500GB+ SSD (database + audio files)

---

## 9. Dependency List

### Backend Dependencies
```
# Web Framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart  # File uploads
websockets>=11.0

# Database
sqlalchemy>=2.0
alembic  # Migrations
psycopg2-binary  # PostgreSQL driver
asyncpg  # Async PostgreSQL

# Task Queue
celery>=5.3.0
redis>=5.0.0

# Audio Processing
pydub>=0.25.1
ffmpeg-python>=0.2.0
silero-vad>=4.0  # Voice Activity Detection
pyannote.audio>=3.0  # Speaker diarization

# YouTube Download
yt-dlp>=2023.10.0

# Utilities
python-dotenv  # Environment variables
pydantic>=2.0  # Data validation
aiofiles  # Async file operations
```

### Frontend Dependencies
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.16.0",
    "react-query": "^3.39.0",
    "axios": "^1.5.0",
    "@mui/material": "^5.14.0",
    "@emotion/react": "^11.11.0",
    "@emotion/styled": "^11.11.0",
    "react-dropzone": "^14.2.0",
    "wavesurfer.js": "^7.3.0",
    "recharts": "^2.8.0",
    "date-fns": "^2.30.0"
  }
}
```

---

## 10. API Authentication & Security

### 10.1 Authentication Strategy (Future)

- **JWT-based authentication**
- **API key support for programmatic access**
- **OAuth2 integration (Google, GitHub)**

### 10.2 Security Measures

1. **Input Validation**
   - File type verification (magic bytes, not just extension)
   - File size limits (configurable, default 500MB)
   - YouTube URL sanitization

2. **Rate Limiting**
   - Upload: 10 files/hour per IP (unauthenticated)
   - API calls: 100 requests/minute per user
   - WebSocket connections: 5 concurrent per user

3. **Data Sanitization**
   - SQL injection prevention (SQLAlchemy ORM)
   - XSS prevention (input escaping)
   - Path traversal protection (file uploads)

4. **CORS Configuration**
   - Whitelist allowed origins
   - Credentials support for authenticated requests

---

## 11. Monitoring & Logging

### 11.1 Logging Strategy

- **Application Logs**: Structured JSON logging with context
- **Access Logs**: HTTP request/response logging
- **Error Logs**: Stack traces with job context
- **Audit Logs**: User actions (upload, delete, export)

### 11.2 Metrics to Track

- **Performance**: Job processing time, queue length
- **Usage**: Uploads per day, total transcription hours
- **Errors**: Failed jobs, error types, recovery rate
- **Resources**: CPU, GPU, memory, disk usage

---

## 12. Testing Strategy

### 12.1 Test Coverage

- **Unit Tests**: Individual functions and utilities
- **Integration Tests**: API endpoints, database operations
- **End-to-End Tests**: Full transcription pipeline
- **Performance Tests**: Load testing with concurrent jobs

### 12.2 Test Cases

1. **Audio Processing**
   - Various input formats
   - Corrupted files
   - Edge cases (very short, very long, silent audio)

2. **Chunking Algorithm**
   - Exact 30s boundaries
   - No mid-word cuts
   - Overlapping chunk handling

3. **Transcription**
   - Single-language audio
   - Multi-language code-switching
   - Multiple speakers

4. **API**
   - Invalid inputs
   - Concurrent requests
   - WebSocket disconnections

---

## 13. Deployment Guide

### 13.1 Docker Deployment

**docker-compose.yml** structure:
```yaml
services:
  web:
    build: ./backend
    ports:
      - "8123:8123"
    depends_on:
      - db
      - redis

  worker:
    build: ./backend
    command: celery -A app.celery worker
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
```

### 13.2 Production Checklist

- [ ] Set environment variables (DATABASE_URL, SECRET_KEY, etc.)
- [ ] Configure reverse proxy (Nginx)
- [ ] Enable HTTPS (Let's Encrypt)
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Set resource limits (Docker, Celery)
- [ ] Enable monitoring (Prometheus/Grafana)
- [ ] Test disaster recovery

---

## 14. Future Enhancements

### 14.1 Advanced AI Features

1. **Automatic Summarization**
   - Generate meeting summaries
   - Extract key points and action items

2. **Sentiment Analysis**
   - Detect speaker emotions
   - Identify tone changes

3. **Entity Recognition**
   - Extract names, dates, locations
   - Link to knowledge bases

### 14.2 Collaboration Features

4. **Team Workspaces**
   - Shared transcription libraries
   - Permission management

5. **Comments & Annotations**
   - Timestamp-based comments
   - Collaborative editing

### 14.3 Integration Features

6. **Calendar Integration**
   - Auto-transcribe meeting recordings
   - Sync with Google Calendar, Outlook

7. **CRM Integration**
   - Link transcriptions to contacts
   - Export to Salesforce, HubSpot

---

## 15. Conclusion

This comprehensive plan outlines a production-ready web interface for the Omnilingual ASR system with:

✅ **Robust Architecture**: Scalable, modular, and maintainable
✅ **Smart Processing**: Word-boundary-aware chunking with VAD
✅ **Rich Features**: Speaker diarization, language detection, multiple formats
✅ **Great UX**: Real-time updates, intuitive UI, multiple export options
✅ **Future-Proof**: Extensible design for advanced AI features

**Total Estimated Development Time**: 10-12 weeks (single developer)
**Recommended Team Size**: 2-3 developers (backend, frontend, ML engineer)

---

## Appendix A: Sample API Requests

### Upload Audio
```bash
curl -X POST http://localhost:8123/api/upload \
  -F "file=@meeting.mp3"
```

### Start Transcription
```bash
curl -X POST http://localhost:8123/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "audio_id": "abc123",
    "model": "LLM_7B",
    "enable_diarization": true
  }'
```

### Get Job Status
```bash
curl http://localhost:8123/api/jobs/job456
```

### Export Transcription
```bash
curl http://localhost:8123/api/jobs/job456/export?format=srt \
  -o subtitles.srt
```

---

## Appendix B: Configuration Examples

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/omniasr
REDIS_URL=redis://localhost:6379/0

# Server
PORT=8123
HOST=0.0.0.0
DEBUG=false

# Processing
MAX_UPLOAD_SIZE=524288000  # 500MB
DEFAULT_MODEL=LLM_7B
CHUNK_DURATION=30
ENABLE_DIARIZATION=true

# Storage
STORAGE_PATH=/var/omniasr/storage
MAX_STORAGE_DAYS=30

# Security
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=http://localhost:3000
```

---

*Last Updated: 2025-11-14*
*Version: 1.0*
