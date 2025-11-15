"""Database models for Omnilingual ASR Web Application."""

from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SourceType(str, PyEnum):
    """Audio source type."""
    UPLOAD = "upload"
    YOUTUBE = "youtube"
    URL = "url"


class JobStatus(str, PyEnum):
    """Processing job status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AudioFile(Base):
    """Audio file metadata."""
    __tablename__ = "audio_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    duration_seconds = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    format = Column(String(50), nullable=True)
    source_type = Column(Enum(SourceType), nullable=False, default=SourceType.UPLOAD)
    source_url = Column(String(1024), nullable=True)
    checksum = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    jobs = relationship("ProcessingJob", back_populates="audio_file", cascade="all, delete-orphan")


class ProcessingJob(Base):
    """Transcription processing job."""
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    audio_file_id = Column(Integer, ForeignKey("audio_files.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.QUEUED, index=True)
    model_name = Column(String(50), nullable=False)  # e.g., "LLM_7B", "CTC_1B"
    language_hint = Column(String(10), nullable=True)  # ISO 639-3 code
    enable_diarization = Column(Boolean, default=False, nullable=False)
    enable_translation = Column(Boolean, default=True, nullable=False)  # Enable translation
    target_language = Column(String(10), default="eng", nullable=False)  # Translation target language
    chunk_duration = Column(Integer, default=30, nullable=False)  # seconds
    progress_percent = Column(Float, default=0.0, nullable=False)
    current_step = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    audio_file = relationship("AudioFile", back_populates="jobs")
    segments = relationship("TranscriptionSegment", back_populates="job", cascade="all, delete-orphan")
    speakers = relationship("Speaker", back_populates="job", cascade="all, delete-orphan")
    languages = relationship("DetectedLanguage", back_populates="job", cascade="all, delete-orphan")
    translations = relationship("Translation", back_populates="job", cascade="all, delete-orphan")


class TranscriptionSegment(Base):
    """Individual transcribed audio segment."""
    __tablename__ = "transcription_segments"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)  # seconds
    end_time = Column(Float, nullable=False)  # seconds
    text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=True)  # Translated text
    confidence = Column(Float, nullable=True)
    speaker_id = Column(Integer, ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True)
    chunk_file_path = Column(String(512), nullable=True)

    # Relationships
    job = relationship("ProcessingJob", back_populates="segments")
    speaker = relationship("Speaker", back_populates="segments")


class Speaker(Base):
    """Identified speaker in audio."""
    __tablename__ = "speakers"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False)
    speaker_label = Column(String(50), nullable=False)  # e.g., "SPEAKER_00"
    custom_name = Column(String(100), nullable=True)  # User-assigned name
    total_speaking_time = Column(Float, default=0.0, nullable=False)  # seconds
    num_segments = Column(Integer, default=0, nullable=False)

    # Relationships
    job = relationship("ProcessingJob", back_populates="speakers")
    segments = relationship("TranscriptionSegment", back_populates="speaker")


class DetectedLanguage(Base):
    """Detected language in audio."""
    __tablename__ = "detected_languages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False)
    language_code = Column(String(10), nullable=False)  # ISO 639-3
    language_name = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    time_percentage = Column(Float, nullable=False)  # Percentage of audio in this language

    # Relationships
    job = relationship("ProcessingJob", back_populates="languages")


class Translation(Base):
    """Translation metadata for transcription."""
    __tablename__ = "translations"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), nullable=False)
    source_language = Column(String(10), nullable=False)  # ISO 639-3 source language
    target_language = Column(String(10), nullable=False)  # ISO 639-3 target language
    full_translated_text = Column(Text, nullable=False)  # Complete translated text
    translation_model = Column(String(100), nullable=True)  # Model used for translation
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    job = relationship("ProcessingJob", back_populates="translations")
