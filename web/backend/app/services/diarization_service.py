"""Speaker diarization service."""

from typing import List, Dict, Optional
from pathlib import Path
import numpy as np


class DiarizationService:
    """
    Speaker diarization service.

    Note: This is a simplified implementation. For production use,
    integrate pyannote.audio for actual speaker diarization.
    """

    def __init__(self, model_name: str = 'pyannote/speaker-diarization'):
        """
        Initialize diarization service.

        Args:
            model_name: Model name for diarization
        """
        self.model_name = model_name
        self.pipeline = None
        self._initialize_pipeline()

    def _initialize_pipeline(self):
        """Initialize diarization pipeline."""
        try:
            # Try to import pyannote.audio
            from pyannote.audio import Pipeline
            # This requires HuggingFace token for model download
            # For now, we'll leave it as optional
            # self.pipeline = Pipeline.from_pretrained(self.model_name)
            pass
        except ImportError:
            print("Warning: pyannote.audio not installed. Diarization will be disabled.")
            self.pipeline = None

    def diarize(
        self,
        audio_path: str,
        num_speakers: Optional[int] = None
    ) -> List[Dict]:
        """
        Perform speaker diarization on audio file.

        Args:
            audio_path: Path to audio file
            num_speakers: Optional number of speakers (if known)

        Returns:
            List of speaker segments with start, end, and speaker label
        """
        if self.pipeline is None:
            # Return mock diarization for testing
            return self._mock_diarization(audio_path)

        try:
            # Run diarization
            diarization = self.pipeline(audio_path)

            # Convert to segment list
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    'start': turn.start,
                    'end': turn.end,
                    'speaker': speaker
                })

            return segments

        except Exception as e:
            print(f"Diarization failed: {str(e)}")
            return self._mock_diarization(audio_path)

    def _mock_diarization(self, audio_path: str) -> List[Dict]:
        """
        Create mock diarization for testing purposes.

        This simple implementation assumes a single speaker.
        In production, replace this with actual pyannote.audio diarization.

        Args:
            audio_path: Path to audio file

        Returns:
            List of mock speaker segments
        """
        # Get audio duration
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            duration = info.duration
        except Exception:
            duration = 60.0  # Default assumption

        # Return single speaker for entire duration
        return [{
            'start': 0.0,
            'end': duration,
            'speaker': 'SPEAKER_00'
        }]

    def map_speakers_to_chunks(
        self,
        speaker_segments: List[Dict],
        chunks: List[Dict]
    ) -> List[str]:
        """
        Map speaker labels to audio chunks.

        Args:
            speaker_segments: Speaker segments from diarization
            chunks: Audio chunks with start/end times

        Returns:
            List of speaker labels corresponding to each chunk
        """
        chunk_speakers = []

        for chunk in chunks:
            chunk_start = chunk['start_time']
            chunk_end = chunk['end_time']
            chunk_mid = (chunk_start + chunk_end) / 2

            # Find the speaker at the midpoint of the chunk
            speaker = 'SPEAKER_00'  # Default
            for segment in speaker_segments:
                if segment['start'] <= chunk_mid <= segment['end']:
                    speaker = segment['speaker']
                    break

            chunk_speakers.append(speaker)

        return chunk_speakers

    def aggregate_speaker_stats(
        self,
        segments: List[Dict]
    ) -> List[Dict]:
        """
        Aggregate statistics for each speaker.

        Args:
            segments: List of transcription segments with speaker labels

        Returns:
            List of speaker statistics
        """
        speakers = {}

        for segment in segments:
            speaker_label = segment.get('speaker_label', 'SPEAKER_00')
            duration = segment['end_time'] - segment['start_time']

            if speaker_label not in speakers:
                speakers[speaker_label] = {
                    'label': speaker_label,
                    'total_time': 0.0,
                    'num_segments': 0
                }

            speakers[speaker_label]['total_time'] += duration
            speakers[speaker_label]['num_segments'] += 1

        return list(speakers.values())
