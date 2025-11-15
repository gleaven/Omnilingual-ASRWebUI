"""Audio upload and management API endpoints."""

import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AudioFile, SourceType
from ..schemas import AudioFileResponse
from ..services.audio_processor import AudioProcessor
from ..core.config import settings

router = APIRouter(prefix="/api/audio", tags=["audio"])
audio_processor = AudioProcessor(storage_path=settings.STORAGE_PATH)


@router.post("/upload", response_model=AudioFileResponse)
async def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload an audio file.

    Args:
        file: Audio file to upload
        db: Database session

    Returns:
        Audio file metadata
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower().lstrip('.')
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Save uploaded file temporarily
    temp_path = Path(settings.STORAGE_PATH) / "temp" / file.filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate audio file
        is_valid, error_msg = audio_processor.validate_audio_file(str(temp_path))
        if not is_valid:
            temp_path.unlink()
            raise HTTPException(status_code=400, detail=error_msg)

        # Calculate checksum
        checksum = audio_processor.calculate_checksum(str(temp_path))

        # Check if file already exists (deduplication)
        existing_file = db.query(AudioFile).filter(AudioFile.checksum == checksum).first()
        if existing_file:
            temp_path.unlink()
            return existing_file

        # Get audio info
        audio_info = audio_processor.get_audio_info(str(temp_path))

        # Move to permanent storage
        final_path = audio_processor.raw_path / f"{checksum}{Path(file.filename).suffix}"
        shutil.move(str(temp_path), str(final_path))

        # Create database record
        audio_file = AudioFile(
            filename=final_path.name,
            original_filename=file.filename,
            file_path=str(final_path),
            file_size=final_path.stat().st_size,
            duration_seconds=audio_info.get('duration'),
            sample_rate=audio_info.get('sample_rate'),
            channels=audio_info.get('channels'),
            format=audio_info.get('format'),
            source_type=SourceType.UPLOAD,
            checksum=checksum
        )

        db.add(audio_file)
        db.commit()
        db.refresh(audio_file)

        return audio_file

    except HTTPException:
        raise
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/{audio_id}", response_model=AudioFileResponse)
def get_audio(audio_id: int, db: Session = Depends(get_db)):
    """
    Get audio file metadata.

    Args:
        audio_id: Audio file ID
        db: Database session

    Returns:
        Audio file metadata
    """
    audio_file = db.query(AudioFile).filter(AudioFile.id == audio_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    return audio_file


@router.get("/", response_model=List[AudioFileResponse])
def list_audio_files(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List all audio files.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of audio file metadata
    """
    audio_files = db.query(AudioFile).order_by(AudioFile.upload_date.desc()).offset(skip).limit(limit).all()
    return audio_files


@router.delete("/{audio_id}")
def delete_audio(audio_id: int, db: Session = Depends(get_db)):
    """
    Delete audio file and all associated data.

    Args:
        audio_id: Audio file ID
        db: Database session

    Returns:
        Success message
    """
    audio_file = db.query(AudioFile).filter(AudioFile.id == audio_id).first()
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    # Delete file from storage
    file_path = Path(audio_file.file_path)
    if file_path.exists():
        file_path.unlink()

    # Delete from database (cascade will delete related records)
    db.delete(audio_file)
    db.commit()

    return {"message": "Audio file deleted successfully"}
