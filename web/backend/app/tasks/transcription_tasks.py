"""Celery tasks for transcription processing."""

import time
from pathlib import Path
from typing import List, Dict
from celery import Task
from sqlalchemy.orm import Session

from .celery_app import celery_app
from ..database import SessionLocal
from ..models import ProcessingJob, JobStatus, TranscriptionSegment, Speaker, DetectedLanguage, Translation
from ..services.audio_processor import AudioProcessor
from ..services.vad_chunker import VADChunker
from ..services.asr_service import ASRService
from ..services.diarization_service import DiarizationService
from ..services.translation_service import TranslationService
from ..services.language_detector import LanguageDetector
from ..core.config import settings


class DatabaseTask(Task):
    """Base task with database session."""
    _db: Session = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=DatabaseTask)
def process_transcription(self, job_id: int):
    """
    Main transcription processing task.

    Args:
        job_id: Database ID of the processing job

    Returns:
        Dictionary with processing results
    """
    db = self.db
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

    if not job:
        raise Exception(f"Job {job_id} not found")

    try:
        # Update job status
        job.status = JobStatus.PROCESSING
        job.current_step = "Initializing"
        job.progress_percent = 0
        db.commit()

        # Initialize services
        audio_processor = AudioProcessor(storage_path=settings.STORAGE_PATH)
        vad_chunker = VADChunker()
        asr_service = ASRService(
            model_name=job.model_name,
            device=settings.DEVICE,
            dtype=settings.DTYPE
        )

        # Step 1: Load and convert audio (10%)
        self.update_state(state='PROGRESS', meta={'progress': 10, 'step': 'Loading audio'})
        job.current_step = "Loading audio"
        job.progress_percent = 10
        db.commit()

        audio_file = job.audio_file
        audio_path = audio_file.file_path

        # Convert to WAV if needed
        if not audio_path.endswith('.wav'):
            wav_path = str(Path(settings.STORAGE_PATH) / "processed" / f"{audio_file.id}.wav")
            audio_processor.convert_to_wav(audio_path, wav_path)
        else:
            wav_path = audio_path

        # Step 2: Load audio data (15%)
        self.update_state(state='PROGRESS', meta={'progress': 15, 'step': 'Processing audio'})
        job.current_step = "Processing audio"
        job.progress_percent = 15
        db.commit()

        audio_data, sr = audio_processor.load_audio(wav_path)

        # Step 3: Smart chunking (25%)
        self.update_state(state='PROGRESS', meta={'progress': 25, 'step': 'Creating chunks'})
        job.current_step = "Creating smart chunks"
        job.progress_percent = 25
        db.commit()

        chunks = vad_chunker.smart_chunk_audio(
            audio_data,
            sr=sr,
            target_duration=job.chunk_duration,
            tolerance=5.0,
            max_duration=40.0,
            overlap=0.5
        )

        # Save chunks to files
        chunks_dir = Path(settings.STORAGE_PATH) / "chunks" / str(job.id)
        chunk_paths = vad_chunker.save_chunks(
            chunks,
            chunks_dir,
            f"audio_{audio_file.id}",
            sr=sr
        )

        # Update chunks with file paths
        for chunk, path in zip(chunks, chunk_paths):
            chunk['file_path'] = path

        # Step 4: Speaker diarization (if enabled) (35%)
        speaker_labels = None
        if job.enable_diarization:
            self.update_state(state='PROGRESS', meta={'progress': 35, 'step': 'Identifying speakers'})
            job.current_step = "Identifying speakers"
            job.progress_percent = 35
            db.commit()

            diarization_service = DiarizationService()
            speaker_segments = diarization_service.diarize(wav_path)
            speaker_labels = diarization_service.map_speakers_to_chunks(speaker_segments, chunks)

        # Step 5: Transcribe chunks (40-90%) - BATCH PROCESSING
        total_chunks = len(chunks)

        # Prepare batch inputs
        chunk_paths = [chunk['file_path'] for chunk in chunks]

        # Update progress to show batch transcription starting
        self.update_state(state='PROGRESS', meta={'progress': 40, 'step': 'Transcribing all chunks (batch mode)'})
        job.current_step = f"Transcribing {total_chunks} chunks in batch mode"
        job.progress_percent = 40
        db.commit()

        # Transcribe all chunks in batch (much faster!)
        try:
            # Use batch size of 4 for optimal GPU/CPU utilization
            batch_size = 4 if total_chunks > 1 else 1
            transcriptions = asr_service.transcribe_batch(
                chunk_paths,
                language=job.language_hint,
                batch_size=batch_size
            )

            # Update progress to 90% after batch completion
            self.update_state(state='PROGRESS', meta={'progress': 90, 'step': 'Batch transcription completed'})
            job.current_step = "Batch transcription completed"
            job.progress_percent = 90
            db.commit()

        except Exception as e:
            print(f"Batch transcription failed: {str(e)}, falling back to sequential")

            # Fallback to sequential processing if batch fails
            transcriptions = []
            for idx, chunk in enumerate(chunks):
                progress = 40 + int((idx / total_chunks) * 50)
                step = f"Transcribing chunk {idx + 1}/{total_chunks}"

                self.update_state(state='PROGRESS', meta={'progress': progress, 'step': step})
                job.current_step = step
                job.progress_percent = progress
                db.commit()

                try:
                    text = asr_service.transcribe(
                        chunk['file_path'],
                        language=job.language_hint
                    )
                    transcriptions.append(text)
                except Exception as e:
                    print(f"Error transcribing chunk {idx}: {str(e)}")
                    transcriptions.append("")

        # Step 6: Save transcription segments (95%)
        self.update_state(state='PROGRESS', meta={'progress': 95, 'step': 'Saving results'})
        job.current_step = "Saving results"
        job.progress_percent = 95
        db.commit()

        # Create speaker records
        if speaker_labels:
            unique_speakers = list(set(speaker_labels))
            speaker_map = {}

            for speaker_label in unique_speakers:
                speaker = Speaker(
                    job_id=job.id,
                    speaker_label=speaker_label,
                    total_speaking_time=0.0,
                    num_segments=0
                )
                db.add(speaker)
                db.flush()  # Get speaker ID
                speaker_map[speaker_label] = speaker.id

        # Save transcription segments
        for idx, (chunk, text) in enumerate(zip(chunks, transcriptions)):
            speaker_id = None
            if speaker_labels and idx < len(speaker_labels):
                speaker_label = speaker_labels[idx]
                speaker_id = speaker_map.get(speaker_label)

            segment = TranscriptionSegment(
                job_id=job.id,
                chunk_index=idx,
                start_time=chunk['start_time'],
                end_time=chunk['end_time'],
                text=text,
                speaker_id=speaker_id,
                chunk_file_path=chunk.get('file_path')
            )
            db.add(segment)

            # Update speaker stats
            if speaker_id:
                speaker = db.query(Speaker).filter(Speaker.id == speaker_id).first()
                if speaker:
                    speaker.total_speaking_time += (chunk['end_time'] - chunk['start_time'])
                    speaker.num_segments += 1

        # Step 7: Detect language (95%)
        self.update_state(state='PROGRESS', meta={'progress': 95, 'step': 'Detecting language'})
        job.current_step = "Detecting language"
        job.progress_percent = 95
        db.commit()

        # Detect language from transcribed text
        if job.language_hint:
            # Use language hint if provided
            source_language = job.language_hint
            lang_name = TranslationService.get_language_name(source_language)
            confidence = 1.0
            print(f"DEBUG: Using language hint: {source_language}")
        else:
            # Detect from transcribed text
            full_text = " ".join(transcriptions)
            print(f"DEBUG: Full text for detection ({len(full_text)} chars): {full_text[:200]}")
            detection_result = LanguageDetector.detect_language(full_text)
            print(f"DEBUG: Detection result: {detection_result}")
            source_language = detection_result['language_code']
            lang_name = detection_result['language_name']
            confidence = detection_result['confidence']
            print(f"DEBUG: Final language: {source_language} ({lang_name})")

        detected_lang = DetectedLanguage(
            job_id=job.id,
            language_code=source_language,
            language_name=lang_name,
            confidence=confidence,
            time_percentage=100.0
        )
        db.add(detected_lang)
        db.commit()

        # Step 8: Translation (if enabled) (96-99%)
        if job.enable_translation and job.target_language != source_language:
            self.update_state(state='PROGRESS', meta={'progress': 96, 'step': 'Translating transcription'})
            job.current_step = "Translating transcription"
            job.progress_percent = 96
            db.commit()

            try:
                # Initialize translation service
                translation_service = TranslationService(
                    device=settings.DEVICE,
                    cache_dir=settings.MODEL_CACHE_DIR
                )

                # Translate in batch for efficiency (transcriptions is already a list of strings)
                translated_texts = translation_service.translate_batch(
                    transcriptions,
                    source_lang=source_language,
                    target_lang=job.target_language,
                    batch_size=4
                )

                # Update segments with translations
                segments = db.query(TranscriptionSegment).filter(
                    TranscriptionSegment.job_id == job.id
                ).order_by(TranscriptionSegment.chunk_index).all()

                for segment, translated_text in zip(segments, translated_texts):
                    segment.translated_text = translated_text

                # Create full translated text
                full_translated_text = " ".join(translated_texts)

                # Save translation record
                translation_record = Translation(
                    job_id=job.id,
                    source_language=source_language,
                    target_language=job.target_language,
                    full_translated_text=full_translated_text,
                    translation_model="facebook/nllb-200-distilled-600M"
                )
                db.add(translation_record)
                db.commit()

                print(f"Translation completed: {source_language} -> {job.target_language}")

            except Exception as e:
                print(f"Translation error: {str(e)}")
                # Continue even if translation fails
                job.current_step = "Translation failed, continuing..."
                db.commit()

        # Complete job (100%)
        job.status = JobStatus.COMPLETED
        job.current_step = "Completed"
        job.progress_percent = 100
        job.completed_at = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first().created_at  # Use current time
        db.commit()

        return {
            'job_id': job.id,
            'status': 'completed',
            'num_chunks': len(chunks),
            'num_speakers': len(speaker_map) if speaker_labels else 0
        }

    except Exception as e:
        # Handle errors
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.current_step = "Failed"
        db.commit()

        raise e
