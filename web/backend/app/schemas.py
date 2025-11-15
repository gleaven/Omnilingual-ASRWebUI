"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


# ============================================================================
# Audio File Schemas
# ============================================================================

class AudioFileBase(BaseModel):
    """Base audio file schema."""
    filename: str
    original_filename: str
    file_size: int
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    format: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None


class AudioFileCreate(AudioFileBase):
    """Schema for creating audio file."""
    file_path: str
    checksum: str


class AudioFileResponse(AudioFileBase):
    """Schema for audio file response."""
    id: int
    upload_date: datetime

    class Config:
        from_attributes = True


# ============================================================================
# YouTube Schemas
# ============================================================================

class YouTubeRequest(BaseModel):
    """Request schema for YouTube download."""
    url: HttpUrl


# ============================================================================
# Transcription Job Schemas
# ============================================================================

class TranscriptionRequest(BaseModel):
    """Request schema for starting transcription."""
    audio_id: int
    model: str = Field(default="CTC_1B", description="Model name: LLM_7B, LLM_3B, LLM_1B, CTC_1B, etc.")
    language_hint: Optional[str] = Field(default=None, description="ISO 639-3 language code")
    enable_diarization: bool = Field(default=False, description="Enable speaker diarization")
    enable_translation: bool = Field(default=True, description="Enable translation")
    target_language: str = Field(default="eng", description="Target language for translation (ISO 639-3)")
    chunk_duration: int = Field(default=30, ge=10, le=40, description="Target chunk duration in seconds")


class JobStatusResponse(BaseModel):
    """Response schema for job status."""
    job_id: int
    status: str
    progress: float
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# Transcription Result Schemas
# ============================================================================

class SpeakerInfo(BaseModel):
    """Speaker information."""
    id: int
    label: str
    custom_name: Optional[str] = None
    total_speaking_time: float
    num_segments: int

    class Config:
        from_attributes = True


class LanguageInfo(BaseModel):
    """Detected language information."""
    code: str
    name: str
    confidence: float
    time_percentage: float

    class Config:
        from_attributes = True


class TranscriptionSegmentResponse(BaseModel):
    """Transcription segment response."""
    start_time: float
    end_time: float
    text: str
    translated_text: Optional[str] = None
    speaker_label: Optional[str] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class TranscriptionResultResponse(BaseModel):
    """Complete transcription result."""
    job_id: int
    status: str
    full_text: str
    full_translated_text: Optional[str] = None
    detected_languages: List[LanguageInfo]
    speakers: List[SpeakerInfo]
    segments: List[TranscriptionSegmentResponse]
    audio_duration: float
    processing_time: Optional[float] = None
    translation_enabled: bool = False
    target_language: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================================
# Job List Schemas
# ============================================================================

class JobListItem(BaseModel):
    """Job list item for dashboard."""
    job_id: int
    audio_filename: str
    status: str
    progress: float
    model_name: str
    created_at: datetime
    duration: Optional[float] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Paginated job list response."""
    items: List[JobListItem]
    total: int
    page: int
    page_size: int


# ============================================================================
# WebSocket Message Schemas
# ============================================================================

class ProgressMessage(BaseModel):
    """WebSocket progress message."""
    type: str = "progress"
    job_id: int
    progress: float
    step: str
    status: str


class ErrorMessage(BaseModel):
    """WebSocket error message."""
    type: str = "error"
    job_id: int
    error: str


# ============================================================================
# Export Schemas
# ============================================================================

class ExportFormat(str):
    """Export format options."""
    TXT = "txt"
    JSON = "json"
    SRT = "srt"
    VTT = "vtt"
    CSV = "csv"
