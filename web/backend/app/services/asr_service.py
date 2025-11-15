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
except ImportError:
    ASRInferencePipeline = None


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

        # Initialize pipeline
        pipeline = ASRInferencePipeline(
            model_card=full_model_name,
            device=self.device,
            dtype=torch_dtype
        )

        return pipeline

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
                    return results[0]
                return str(results)

            # For batch, return all results
            return results

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
            return results

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
