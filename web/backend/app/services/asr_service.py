"""ASR inference service wrapping Omnilingual ASR models."""

import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Union
import numpy as np
import torch

# Add parent repo to path to import omnilingual_asr
# In Docker: /app/repo/src contains omnilingual_asr
repo_path = Path("/app/repo/src")
if not repo_path.exists():
    # Fallback for local development
    repo_path = Path(__file__).parent.parent.parent.parent / "repo" / "src"
sys.path.insert(0, str(repo_path))

try:
    from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
    from omnilingual_asr.models.wav2vec2_llama.model import Wav2Vec2LlamaBeamSearchConfig
except ImportError:
    ASRInferencePipeline = None
    Wav2Vec2LlamaBeamSearchConfig = None


class ASRService:
    """
    ASR inference service for transcription.

    Wraps the Omnilingual ASR inference pipeline with a simplified interface.
    """

    # Model name mappings
    MODEL_MAP = {
        'LLM_7B': 'omniASR_LLM_7B',
        'LLM_3B': 'omniASR_LLM_3B',
        'LLM_1B': 'omniASR_LLM_1B',
        'LLM_300M': 'omniASR_LLM_300M',
        'CTC_7B': 'omniASR_CTC_7B',
        'CTC_3B': 'omniASR_CTC_3B',
        'CTC_1B': 'omniASR_CTC_1B',
        'CTC_300M': 'omniASR_CTC_300M',
    }

    def __init__(
        self,
        model_name: str = 'LLM_7B',
        device: str = 'cuda',
        dtype: str = 'float32'
    ):
        """
        Initialize ASR service.

        Args:
            model_name: Model name (e.g., 'LLM_7B', 'CTC_1B')
            device: Device to use ('cuda' or 'cpu')
            dtype: Data type ('float32' or 'bfloat16')
        """
        if ASRInferencePipeline is None:
            raise ImportError(
                "Could not import omnilingual_asr. "
                "Make sure the repo is in the correct location."
            )

        self.model_name = model_name
        self.device = device if torch.cuda.is_available() else 'cpu'
        self.dtype = dtype

        # Initialize pipeline
        self.pipeline = self._load_pipeline()

    def _load_pipeline(self) -> ASRInferencePipeline:
        """Load ASR inference pipeline."""
        # Get full model name
        full_model_name = self.MODEL_MAP.get(self.model_name, self.model_name)

        # Convert dtype string to torch dtype
        dtype_map = {
            'float32': torch.float32,
            'bfloat16': torch.bfloat16
        }
        torch_dtype = dtype_map.get(self.dtype, torch.float32)

        # Configure beam search with more aggressive repetition detection
        # for LLM models to prevent repetition loops
        beam_search_config = None
        if 'LLM' in self.model_name and Wav2Vec2LlamaBeamSearchConfig is not None:
            beam_search_config = Wav2Vec2LlamaBeamSearchConfig(
                nbest=1,
                length_norm=False,
                # More aggressive compression detection to prevent repetition loops
                compression_window=50,  # Smaller window (default: 100)
                compression_threshold=2.5,  # Lower threshold = more sensitive (default: 4.0)
            )

        # Initialize pipeline
        pipeline = ASRInferencePipeline(
            model_card=full_model_name,
            device=self.device,
            dtype=torch_dtype,
            beam_search_config=beam_search_config,
        )

        return pipeline

    @staticmethod
    def _clean_repetitions(text: str, max_repeats: int = 3) -> str:
        """
        Clean up repetitive phrases in transcription output.

        LLM-based models can sometimes get stuck in loops, generating the same
        phrase over and over. This detects and cleans up such patterns.

        Args:
            text: Input text that may contain repetitions
            max_repeats: Maximum number of times a phrase should appear consecutively

        Returns:
            Cleaned text with repetitions removed
        """
        if not text or len(text) < 10:
            return text

        # Split into words for word-level repetition detection
        words = text.split()
        if len(words) < 6:
            return text

        # Try to find repeated patterns of different lengths (2-10 words)
        cleaned = False
        for pattern_len in range(2, min(11, len(words) // 3)):
            i = 0
            new_words = []
            while i < len(words):
                # Check if we have a repeating pattern starting at position i
                pattern = words[i:i + pattern_len]
                if len(pattern) < pattern_len:
                    new_words.extend(words[i:])
                    break

                # Count how many times this pattern repeats
                repeat_count = 1
                j = i + pattern_len
                while j + pattern_len <= len(words):
                    if words[j:j + pattern_len] == pattern:
                        repeat_count += 1
                        j += pattern_len
                    else:
                        break

                # If too many repeats, limit them
                if repeat_count > max_repeats:
                    # Keep only max_repeats occurrences
                    for _ in range(max_repeats):
                        new_words.extend(pattern)
                    i = j
                    cleaned = True
                else:
                    new_words.append(words[i])
                    i += 1

            if cleaned:
                words = new_words
                cleaned = False  # Reset for next pattern length

        result = ' '.join(words)

        # Also check for character-level repetitions (rare but possible)
        # This catches cases like "...المتحدة المتحدة المتحدة..."
        import re
        # Find phrases repeated more than max_repeats times
        result = re.sub(r'(\b\S+(?:\s+\S+){0,5}?\s*)(\1){' + str(max_repeats) + r',}',
                       r'\1' * max_repeats, result)

        return result.strip()

    def transcribe(
        self,
        audio: Union[str, np.ndarray, bytes],
        language: Optional[str] = None,
        batch_size: int = 1
    ) -> str:
        """
        Transcribe audio file or data.

        Args:
            audio: Audio file path, numpy array, or bytes
            language: Optional language hint (e.g., 'eng_Latn', 'fra_Latn')
            batch_size: Batch size for processing

        Returns:
            Transcribed text
        """
        try:
            # Pipeline expects a list of audio inputs
            # and a list of language codes (or None)
            if isinstance(audio, (list, tuple)):
                # Batch processing
                audio_list = audio
                lang_list = [language] * len(audio_list) if language else None
            else:
                # Single audio - wrap in list
                audio_list = [audio]
                lang_list = [language] if language else None

            # Transcribe using the pipeline
            results = self.pipeline.transcribe(
                audio_list,
                lang=lang_list,
                batch_size=batch_size
            )

            # For single audio, return first result
            if not isinstance(audio, (list, tuple)):
                if isinstance(results, list) and len(results) > 0:
                    result = results[0]
                else:
                    result = str(results)
                # Clean up any repetition loops
                return self._clean_repetitions(result)

            # For batch, return all results (cleaned)
            return [self._clean_repetitions(r) for r in results]

        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")

    def transcribe_batch(
        self,
        audio_list: List[Union[str, np.ndarray]],
        language: Optional[str] = None,
        batch_size: int = 4
    ) -> List[str]:
        """
        Transcribe multiple audio files/chunks in batch.

        Args:
            audio_list: List of audio file paths or numpy arrays
            language: Optional language hint (e.g., 'eng_Latn', 'fra_Latn')
            batch_size: Batch size for processing

        Returns:
            List of transcribed texts
        """
        try:
            # Prepare language list
            lang_list = [language] * len(audio_list) if language else None

            results = self.pipeline.transcribe(
                audio_list,
                lang=lang_list,
                batch_size=batch_size
            )
            # Clean up any repetition loops in results
            return [self._clean_repetitions(r) for r in results]

        except Exception as e:
            raise Exception(f"Batch transcription failed: {str(e)}")

    def detect_language(self, audio: Union[str, np.ndarray]) -> Dict:
        """
        Detect language from audio.

        Args:
            audio: Audio file path or numpy array

        Returns:
            Dictionary with language code, name, and confidence
        """
        # For now, return a placeholder
        # The LLM models can implicitly detect language
        # We would need to extract this from model outputs
        return {
            'code': 'eng',
            'name': 'English',
            'confidence': 0.95
        }

    @staticmethod
    def get_available_models() -> List[str]:
        """
        Get list of available model names.

        Returns:
            List of model names
        """
        return list(ASRService.MODEL_MAP.keys())

    @staticmethod
    def get_model_info(model_name: str) -> Dict:
        """
        Get information about a model.

        Args:
            model_name: Model name

        Returns:
            Dictionary with model information
        """
        model_info = {
            'LLM_7B': {
                'size': '7B parameters',
                'type': 'LLM',
                'quality': 'Best',
                'speed': 'Slow',
                'description': 'Highest quality transcription'
            },
            'LLM_3B': {
                'size': '3B parameters',
                'type': 'LLM',
                'quality': 'Very Good',
                'speed': 'Medium',
                'description': 'Balanced quality and speed'
            },
            'LLM_1B': {
                'size': '1B parameters',
                'type': 'LLM',
                'quality': 'Good',
                'speed': 'Fast',
                'description': 'Good quality, faster processing'
            },
            'CTC_1B': {
                'size': '1B parameters',
                'type': 'CTC',
                'quality': 'Good',
                'speed': 'Very Fast',
                'description': 'Fast transcription, good for real-time'
            },
        }

        return model_info.get(model_name, {
            'size': 'Unknown',
            'type': 'Unknown',
            'quality': 'Unknown',
            'speed': 'Unknown',
            'description': 'Model information not available'
        })
