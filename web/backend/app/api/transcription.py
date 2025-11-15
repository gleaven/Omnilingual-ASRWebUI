"""Transcription job API endpoints."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import (
    ProcessingJob,
    AudioFile,
    JobStatus,
    TranscriptionSegment,
    Speaker,
    DetectedLanguage,
    Translation
)
from ..schemas import (
    TranscriptionRequest,
    JobStatusResponse,
    TranscriptionResultResponse,
    JobListResponse,
    JobListItem,
    SpeakerInfo,
    LanguageInfo,
    TranscriptionSegmentResponse
)
from ..tasks.transcription_tasks import process_transcription

router = APIRouter(prefix="/api", tags=["transcription"])


@router.post("/transcribe", response_model=JobStatusResponse)
def create_transcription_job(
    request: TranscriptionRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new transcription job.

    Args:
        request: Transcription request parameters
        db: Database session

    Returns:
        Job status information
    """
    # Validate audio file exists
    audio_file = db.query(AudioFile).filter(AudioFile.id == request.audio_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    # Create job record
    job = ProcessingJob(
        audio_file_id=request.audio_id,
        status=JobStatus.QUEUED,
        model_name=request.model,
        language_hint=request.language_hint,
        enable_diarization=request.enable_diarization,
        enable_translation=request.enable_translation,
        target_language=request.target_language,
        chunk_duration=request.chunk_duration,
        progress_percent=0.0
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue transcription task
    try:
        process_transcription.delay(job.id)
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_message = f"Failed to queue task: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress_percent,
        current_step=job.current_step,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get job status and progress.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Job status information
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress_percent,
        current_step=job.current_step,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


@router.get("/jobs/{job_id}/result", response_model=TranscriptionResultResponse)
def get_transcription_result(job_id: int, db: Session = Depends(get_db)):
    """
    Get complete transcription result.

    Args:
        job_id: Job ID
        db: Database session

    Returns:
        Complete transcription with segments, speakers, and languages
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed yet. Status: {job.status.value}"
        )

    # Get segments
    segments = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.job_id == job_id
    ).order_by(TranscriptionSegment.chunk_index).all()

    # Get speakers
    speakers = db.query(Speaker).filter(Speaker.job_id == job_id).all()

    # Get detected languages
    languages = db.query(DetectedLanguage).filter(DetectedLanguage.job_id == job_id).all()

    # Create speaker label map
    speaker_map = {s.id: s.speaker_label for s in speakers}

    # Get translation if available
    translation = db.query(Translation).filter(Translation.job_id == job_id).first()

    # Build response
    segment_responses = []
    full_text_parts = []

    for segment in segments:
        speaker_label = None
        if segment.speaker_id and segment.speaker_id in speaker_map:
            speaker_label = speaker_map[segment.speaker_id]

        segment_responses.append(TranscriptionSegmentResponse(
            start_time=segment.start_time,
            end_time=segment.end_time,
            text=segment.text,
            translated_text=segment.translated_text,
            speaker_label=speaker_label,
            confidence=segment.confidence
        ))

        full_text_parts.append(segment.text)

    # Compile full text
    full_text = " ".join(full_text_parts)
    full_translated_text = translation.full_translated_text if translation else None

    # Speaker info
    speaker_infos = [
        SpeakerInfo(
            id=s.id,
            label=s.speaker_label,
            custom_name=s.custom_name,
            total_speaking_time=s.total_speaking_time,
            num_segments=s.num_segments
        )
        for s in speakers
    ]

    # Language info
    language_infos = [
        LanguageInfo(
            code=lang.language_code,
            name=lang.language_name,
            confidence=lang.confidence,
            time_percentage=lang.time_percentage
        )
        for lang in languages
    ]

    # Calculate processing time
    processing_time = None
    if job.started_at and job.completed_at:
        processing_time = (job.completed_at - job.started_at).total_seconds()

    return TranscriptionResultResponse(
        job_id=job.id,
        status=job.status.value,
        full_text=full_text,
        full_translated_text=full_translated_text,
        detected_languages=language_infos,
        speakers=speaker_infos,
        segments=segment_responses,
        audio_duration=job.audio_file.duration_seconds or 0,
        processing_time=processing_time,
        translation_enabled=job.enable_translation,
        target_language=job.target_language if job.enable_translation else None
    )


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List transcription jobs with optional filtering.

    Args:
        status: Filter by job status (optional)
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        Paginated list of jobs
    """
    query = db.query(ProcessingJob)

    # Filter by status if provided
    if status:
        try:
            status_enum = JobStatus(status)
            query = query.filter(ProcessingJob.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Get total count
    total = query.count()

    # Get jobs with pagination
    jobs = query.order_by(desc(ProcessingJob.created_at)).offset(skip).limit(limit).all()

    # Build response items
    items = []
    for job in jobs:
        items.append(JobListItem(
            job_id=job.id,
            audio_filename=job.audio_file.original_filename,
            status=job.status.value,
            progress=job.progress_percent,
            model_name=job.model_name,
            created_at=job.created_at,
            duration=job.audio_file.duration_seconds
        ))

    return JobListResponse(
        items=items,
        total=total,
        page=skip // limit + 1,
        page_size=limit
    )


@router.get("/jobs/{job_id}/export")
def export_transcription(
    job_id: int,
    format: str = Query("txt", regex="^(txt|json|srt|vtt|csv)$"),
    db: Session = Depends(get_db)
):
    """
    Export transcription in various formats.

    Args:
        job_id: Job ID
        format: Export format (txt, json, srt, vtt, csv)
        db: Database session

    Returns:
        Transcription file in requested format
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")

    # Get segments
    segments = db.query(TranscriptionSegment).filter(
        TranscriptionSegment.job_id == job_id
    ).order_by(TranscriptionSegment.chunk_index).all()

    # Get speaker map
    speakers = db.query(Speaker).filter(Speaker.job_id == job_id).all()
    speaker_map = {s.id: s.speaker_label for s in speakers}

    # Get detected language and translation info
    detected_lang = db.query(DetectedLanguage).filter(DetectedLanguage.job_id == job_id).first()
    translation = db.query(Translation).filter(Translation.job_id == job_id).first()

    if format == "txt":
        # Plain text format with header
        text_parts = []

        # Add header with language information
        if detected_lang:
            text_parts.append(f"Original Language: {detected_lang.language_name} ({detected_lang.language_code})")
        if translation:
            text_parts.append(f"Translated to: {translation.target_language.upper()}")
        if detected_lang or translation:
            text_parts.append("=" * 60)
            text_parts.append("")

        # Add segments
        for segment in segments:
            speaker_label = speaker_map.get(segment.speaker_id, "")
            prefix = f"{speaker_label}: " if speaker_label else ""

            # Original text
            text_parts.append(f"{prefix}{segment.text}")

            # Translation if available
            if segment.translated_text:
                text_parts.append(f"  [Translation: {segment.translated_text}]")

            text_parts.append("")  # Empty line between segments

        content = "\n".join(text_parts)
        return PlainTextResponse(content, media_type="text/plain")

    elif format == "json":
        # Get full result
        result = get_transcription_result(job_id, db)
        return JSONResponse(content=result.dict())

    elif format == "srt":
        # SubRip subtitle format with translations
        srt_parts = []
        for idx, segment in enumerate(segments, 1):
            start = _format_srt_time(segment.start_time)
            end = _format_srt_time(segment.end_time)
            text = segment.text

            # Include translation if available
            if segment.translated_text:
                text = f"{text}\n[{segment.translated_text}]"

            srt_parts.append(f"{idx}\n{start} --> {end}\n{text}\n")

        content = "\n".join(srt_parts)
        return PlainTextResponse(content, media_type="text/plain")

    elif format == "vtt":
        # WebVTT subtitle format with translations
        vtt_parts = ["WEBVTT"]

        # Add metadata
        if detected_lang:
            vtt_parts.append(f"NOTE Original Language: {detected_lang.language_name}")
        if translation:
            vtt_parts.append(f"NOTE Translated to: {translation.target_language.upper()}")
        vtt_parts.append("")

        for segment in segments:
            start = _format_vtt_time(segment.start_time)
            end = _format_vtt_time(segment.end_time)
            text = segment.text

            # Include translation if available
            if segment.translated_text:
                text = f"{text}\n[{segment.translated_text}]"

            vtt_parts.append(f"{start} --> {end}\n{text}\n")

        content = "\n".join(vtt_parts)
        return PlainTextResponse(content, media_type="text/vtt")

    elif format == "csv":
        # CSV format with translations
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Add header with language info
        if detected_lang and translation:
            writer.writerow([f"Original Language: {detected_lang.language_name} ({detected_lang.language_code})"])
            writer.writerow([f"Translated to: {translation.target_language.upper()}"])
            writer.writerow([])

        # Column headers
        if translation:
            writer.writerow(["Start Time", "End Time", "Speaker", "Original Text", "Translation"])
        else:
            writer.writerow(["Start Time", "End Time", "Speaker", "Text"])

        # Data rows
        for segment in segments:
            speaker_label = speaker_map.get(segment.speaker_id, "")
            if segment.translated_text:
                writer.writerow([
                    segment.start_time,
                    segment.end_time,
                    speaker_label,
                    segment.text,
                    segment.translated_text
                ])
            else:
                writer.writerow([
                    segment.start_time,
                    segment.end_time,
                    speaker_label,
                    segment.text
                ])

        content = output.getvalue()
        return PlainTextResponse(content, media_type="text/csv")


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """
    Delete a transcription job and all associated data.

    Args:
        job_id: Job ID to delete
        db: Database session

    Returns:
        Success message
    """
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete the job (cascade will delete segments, speakers, translations, etc.)
    db.delete(job)
    db.commit()

    return {"message": f"Job {job_id} deleted successfully"}


def _format_srt_time(seconds: float) -> str:
    """Format time for SRT format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_time(seconds: float) -> str:
    """Format time for WebVTT format (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
