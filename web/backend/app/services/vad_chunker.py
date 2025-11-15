"""Voice Activity Detection and Smart Chunking Service."""

import torch
import numpy as np
from typing import List, Dict, Tuple
from pathlib import Path


class VADChunker:
    """
    Voice Activity Detection and Smart Audio Chunking.

    Uses Silero VAD for detecting speech segments and creates
    intelligent chunks that respect word boundaries.
    """

    def __init__(self, model_name: str = 'silero_vad'):
        """
        Initialize VAD chunker.

        Args:
            model_name: Name of the VAD model to use
        """
        # Load Silero VAD model
        self.model, self.utils = self._load_vad_model()
        self.get_speech_timestamps = self.utils[0]
        self.sampling_rate = 16000  # Silero VAD expects 16kHz

    def _load_vad_model(self):
        """Load Silero VAD model from torch hub."""
        try:
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            return model, utils
        except Exception as e:
            raise Exception(f"Failed to load VAD model: {str(e)}")

    def detect_speech_segments(
        self,
        audio: np.ndarray,
        sr: int = 16000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100
    ) -> List[Dict]:
        """
        Detect speech segments using VAD.

        Args:
            audio: Audio data as numpy array
            sr: Sample rate (will resample if not 16kHz)
            threshold: Speech probability threshold (0-1)
            min_speech_duration_ms: Minimum speech duration to keep
            min_silence_duration_ms: Minimum silence duration between segments

        Returns:
            List of speech segments with start/end times in seconds
        """
        # Ensure audio is float32 and mono
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Resample if needed
        if sr != self.sampling_rate:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sampling_rate)

        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio)

        # Get speech timestamps
        speech_timestamps = self.get_speech_timestamps(
            audio_tensor,
            self.model,
            threshold=threshold,
            sampling_rate=self.sampling_rate,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            return_seconds=False  # Return in samples
        )

        # Convert to seconds and create segments
        segments = []
        for ts in speech_timestamps:
            segments.append({
                'start': ts['start'] / self.sampling_rate,
                'end': ts['end'] / self.sampling_rate
            })

        return segments

    def find_best_pause(
        self,
        speech_segments: List[Dict],
        min_time: float,
        max_time: float,
        ideal_time: float
    ) -> Tuple[float, bool]:
        """
        Find the best pause (silence) within a time window.

        Args:
            speech_segments: List of speech segments from VAD
            min_time: Minimum acceptable time for split
            max_time: Maximum acceptable time for split
            ideal_time: Ideal target time for split

        Returns:
            Tuple of (best_split_time, found_good_pause)
        """
        # Find all silence periods within the window
        pauses = []

        for i in range(len(speech_segments) - 1):
            pause_start = speech_segments[i]['end']
            pause_end = speech_segments[i + 1]['start']
            pause_duration = pause_end - pause_start

            # Only consider pauses >= 200ms
            if pause_duration >= 0.2:
                pause_mid = (pause_start + pause_end) / 2

                # Check if pause is within our window
                if min_time <= pause_mid <= max_time:
                    # Score based on proximity to ideal time and pause duration
                    time_score = 1.0 - abs(pause_mid - ideal_time) / (max_time - min_time)
                    duration_score = min(pause_duration / 1.0, 1.0)  # Prefer longer pauses
                    combined_score = 0.7 * time_score + 0.3 * duration_score

                    pauses.append({
                        'time': pause_mid,
                        'duration': pause_duration,
                        'score': combined_score
                    })

        if pauses:
            # Return the highest-scoring pause
            best_pause = max(pauses, key=lambda x: x['score'])
            return best_pause['time'], True

        return ideal_time, False

    def smart_chunk_audio(
        self,
        audio: np.ndarray,
        sr: int = 16000,
        target_duration: float = 30.0,
        tolerance: float = 5.0,
        max_duration: float = 40.0,
        overlap: float = 0.5
    ) -> List[Dict]:
        """
        Create smart audio chunks that respect word boundaries.

        Args:
            audio: Audio data as numpy array
            sr: Sample rate
            target_duration: Target chunk duration in seconds
            tolerance: Acceptable deviation from target (±seconds)
            max_duration: Maximum chunk duration (ASR model limit)
            overlap: Overlap between chunks in seconds

        Returns:
            List of chunk dictionaries with audio data and metadata
        """
        total_duration = len(audio) / sr

        # Detect speech segments
        speech_segments = self.detect_speech_segments(audio, sr)

        if not speech_segments:
            # No speech detected, return whole audio as single chunk
            return [{
                'audio': audio,
                'start_time': 0.0,
                'end_time': total_duration,
                'chunk_index': 0,
                'has_speech': False
            }]

        chunks = []
        current_start = 0.0
        chunk_index = 0

        while current_start < total_duration:
            # Calculate ideal end point
            ideal_end = current_start + target_duration
            min_end = current_start + (target_duration - tolerance)
            max_end = min(current_start + (target_duration + tolerance), total_duration)

            # Don't create tiny final chunks
            if total_duration - current_start < target_duration / 2:
                ideal_end = total_duration
                chunk_end = total_duration
            else:
                # Find best pause within tolerance window
                chunk_end, found_pause = self.find_best_pause(
                    speech_segments,
                    min_time=min_end,
                    max_time=max_end,
                    ideal_time=ideal_end
                )

                # If no good pause found, extend to next pause or max limit
                if not found_pause:
                    # Find next pause after ideal_end
                    next_pause = None
                    for i in range(len(speech_segments) - 1):
                        pause_mid = (speech_segments[i]['end'] + speech_segments[i + 1]['start']) / 2
                        if pause_mid > ideal_end:
                            next_pause = pause_mid
                            break

                    if next_pause and next_pause <= current_start + max_duration:
                        chunk_end = next_pause
                    else:
                        chunk_end = min(current_start + max_duration, total_duration)

            # Extract audio chunk with overlap
            start_sample = int(current_start * sr)
            end_sample = int(min(chunk_end + overlap, total_duration) * sr)
            chunk_audio = audio[start_sample:end_sample]

            chunks.append({
                'audio': chunk_audio,
                'start_time': current_start,
                'end_time': chunk_end,
                'chunk_index': chunk_index,
                'has_speech': True,
                'duration': chunk_end - current_start
            })

            chunk_index += 1
            current_start = chunk_end

            # Break if we've reached the end
            if chunk_end >= total_duration:
                break

        return chunks

    def save_chunks(
        self,
        chunks: List[Dict],
        output_dir: Path,
        base_name: str,
        sr: int = 16000
    ) -> List[str]:
        """
        Save audio chunks to files.

        Args:
            chunks: List of chunk dictionaries
            output_dir: Directory to save chunks
            base_name: Base filename for chunks
            sr: Sample rate

        Returns:
            List of saved file paths
        """
        import soundfile as sf

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []
        for chunk in chunks:
            chunk_filename = f"{base_name}_chunk_{chunk['chunk_index']:04d}.wav"
            chunk_path = output_dir / chunk_filename

            sf.write(str(chunk_path), chunk['audio'], sr, subtype='PCM_16')
            saved_paths.append(str(chunk_path))

        return saved_paths
