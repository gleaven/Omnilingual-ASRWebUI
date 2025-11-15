"""YouTube audio extraction API endpoints."""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AudioFile, SourceType
from ..schemas import YouTubeRequest, AudioFileResponse
from ..services.youtube_downloader import YouTubeDownloader
from ..services.audio_processor import AudioProcessor
from ..core.config import settings

router = APIRouter(prefix="/api/youtube", tags=["youtube"])
youtube_dl = YouTubeDownloader(output_dir=str(Path(settings.STORAGE_PATH) / "youtube"))
audio_processor = AudioProcessor(storage_path=settings.STORAGE_PATH)


@router.post("/extract", response_model=AudioFileResponse)
def extract_youtube_audio(
    request: YouTubeRequest,
    db: Session = Depends(get_db)
):
    """
    Extract audio from YouTube video.

    Args:
        request: YouTube URL request
        db: Database session

    Returns:
        Audio file metadata
    """
    url = str(request.url)

    # Validate YouTube URL
    if not youtube_dl.validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        # Download audio from YouTube
        result = youtube_dl.download_audio(url)

        # Get audio file path
        audio_path = Path(result['file_path'])

        if not audio_path.exists():
            raise HTTPException(status_code=500, detail="Audio extraction failed")

        # Calculate checksum
        checksum = audio_processor.calculate_checksum(str(audio_path))

        # Check if already exists
        existing_file = db.query(AudioFile).filter(AudioFile.checksum == checksum).first()
        if existing_file:
            # Clean up downloaded file
            audio_path.unlink()
            return existing_file

        # Get audio info
        audio_info = audio_processor.get_audio_info(str(audio_path))

        # Create database record
        audio_file = AudioFile(
            filename=audio_path.name,
            original_filename=f"{result['title']}.wav",
            file_path=str(audio_path),
            file_size=audio_path.stat().st_size,
            duration_seconds=audio_info.get('duration') or result.get('duration'),
            sample_rate=audio_info.get('sample_rate'),
            channels=audio_info.get('channels'),
            format=audio_info.get('format'),
            source_type=SourceType.YOUTUBE,
            source_url=url,
            checksum=checksum
        )

        db.add(audio_file)
        db.commit()
        db.refresh(audio_file)

        return audio_file

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube extraction failed: {str(e)}")
