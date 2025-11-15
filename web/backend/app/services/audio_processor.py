"""Audio processing service for format conversion and validation."""

import os
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
import soundfile as sf
import librosa
import numpy as np
from pydub import AudioSegment

from ..core.config import settings


class AudioProcessor:
    """Handle audio file processing and conversion."""

    SUPPORTED_FORMATS = settings.ALLOWED_EXTENSIONS

    def __init__(self, storage_path: str = None):
        """
        Initialize audio processor.

        Args:
            storage_path: Path to store processed audio files
        """
        self.storage_path = Path(storage_path or settings.STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.raw_path = self.storage_path / "raw"
        self.processed_path = self.storage_path / "processed"
        self.chunks_path = self.storage_path / "chunks"

        self.raw_path.mkdir(exist_ok=True)
        self.processed_path.mkdir(exist_ok=True)
        self.chunks_path.mkdir(exist_ok=True)

    def calculate_checksum(self, file_path: str) -> str:
        """
        Calculate SHA-256 checksum of file.

        Args:
            file_path: Path to file

        Returns:
            Hex string of SHA-256 hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def validate_audio_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate audio file format and size.

        Args:
            file_path: Path to audio file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file exists
        if not os.path.exists(file_path):
            return False, "File does not exist"

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > settings.MAX_UPLOAD_SIZE:
            return False, f"File too large (max {settings.MAX_UPLOAD_SIZE / (1024**2):.0f}MB)"

        # Check extension
        ext = Path(file_path).suffix.lower().lstrip('.')
        if ext not in self.SUPPORTED_FORMATS:
            return False, f"Unsupported format .{ext}"

        return True, None

    def get_audio_info(self, file_path: str) -> Dict:
        """
        Extract audio file metadata using ffprobe.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary with audio metadata
        """
        try:
            # Use ffprobe to get audio info
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"ffprobe failed: {result.stderr}")

            import json
            data = json.loads(result.stdout)

            # Find audio stream
            audio_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    audio_stream = stream
                    break

            if not audio_stream:
                raise Exception("No audio stream found")

            format_info = data.get('format', {})

            return {
                'duration': float(format_info.get('duration', 0)),
                'sample_rate': int(audio_stream.get('sample_rate', 0)),
                'channels': int(audio_stream.get('channels', 1)),
                'format': audio_stream.get('codec_name', 'unknown'),
                'bitrate': int(format_info.get('bit_rate', 0)),
            }

        except Exception as e:
            # Fallback to soundfile
            try:
                info = sf.info(file_path)
                return {
                    'duration': info.duration,
                    'sample_rate': info.samplerate,
                    'channels': info.channels,
                    'format': info.format,
                    'bitrate': 0,
                }
            except Exception:
                raise Exception(f"Failed to extract audio info: {str(e)}")

    def convert_to_wav(self, input_path: str, output_path: str, target_sr: int = 16000) -> str:
        """
        Convert audio file to WAV format (16kHz, mono, 16-bit PCM).

        Args:
            input_path: Path to input audio file
            output_path: Path to output WAV file
            target_sr: Target sample rate (default 16000 Hz for ASR)

        Returns:
            Path to converted WAV file
        """
        try:
            # Use ffmpeg for conversion (most reliable for all formats)
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ar', str(target_sr),  # Sample rate
                '-ac', '1',  # Mono
                '-c:a', 'pcm_s16le',  # 16-bit PCM
                '-y',  # Overwrite output file
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"ffmpeg conversion failed: {result.stderr}")

            return output_path

        except Exception as e:
            # Fallback to librosa
            try:
                audio, sr = librosa.load(input_path, sr=target_sr, mono=True)
                sf.write(output_path, audio, target_sr, subtype='PCM_16')
                return output_path
            except Exception:
                raise Exception(f"Audio conversion failed: {str(e)}")

    def load_audio(self, file_path: str, sr: int = 16000) -> Tuple[np.ndarray, int]:
        """
        Load audio file as numpy array.

        Args:
            file_path: Path to audio file
            sr: Target sample rate

        Returns:
            Tuple of (audio_array, sample_rate)
        """
        audio, sample_rate = librosa.load(file_path, sr=sr, mono=True)
        return audio, sample_rate

    def save_audio_chunk(self, audio: np.ndarray, sr: int, output_path: str) -> str:
        """
        Save audio chunk to file.

        Args:
            audio: Audio data as numpy array
            sr: Sample rate
            output_path: Path to output file

        Returns:
            Path to saved file
        """
        sf.write(output_path, audio, sr, subtype='PCM_16')
        return output_path

    def extract_audio_from_video(self, video_path: str, output_path: str) -> str:
        """
        Extract audio from video file.

        Args:
            video_path: Path to video file
            output_path: Path to output audio file

        Returns:
            Path to extracted audio file
        """
        return self.convert_to_wav(video_path, output_path)
