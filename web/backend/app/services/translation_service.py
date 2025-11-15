"""Translation service using pre-trained translation models."""

import os
from typing import List, Dict, Optional
from pathlib import Path

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class TranslationService:
    """
    Translation service for multilingual text translation.

    Uses Facebook's NLLB-200 model for high-quality translation
    across 200+ languages.
    """

    # Language code mapping (ISO 639-3 to NLLB codes)
    LANG_MAP = {
        'eng': 'eng_Latn',  # English
        'spa': 'spa_Latn',  # Spanish
        'fra': 'fra_Latn',  # French
        'deu': 'deu_Latn',  # German
        'ita': 'ita_Latn',  # Italian
        'por': 'por_Latn',  # Portuguese
        'rus': 'rus_Cyrl',  # Russian
        'jpn': 'jpn_Jpan',  # Japanese
        'kor': 'kor_Hang',  # Korean
        'zho': 'zho_Hans',  # Chinese (Simplified)
        'ara': 'arb_Arab',  # Arabic
        'hin': 'hin_Deva',  # Hindi
        'tur': 'tur_Latn',  # Turkish
        'vie': 'vie_Latn',  # Vietnamese
        'pol': 'pol_Latn',  # Polish
        'nld': 'nld_Latn',  # Dutch
        'swe': 'swe_Latn',  # Swedish
        'ind': 'ind_Latn',  # Indonesian
        'tha': 'tha_Thai',  # Thai
        'ukr': 'ukr_Cyrl',  # Ukrainian
    }

    def __init__(
        self,
        model_name: str = "facebook/nllb-200-distilled-600M",
        device: str = "cuda",
        cache_dir: Optional[str] = None
    ):
        """
        Initialize translation service.

        Args:
            model_name: HuggingFace model name (default: NLLB-200 600M distilled)
            device: Device to use ('cuda' or 'cpu')
            cache_dir: Model cache directory
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers library is required for translation. "
                "Install with: pip install transformers"
            )

        self.model_name = model_name
        self.device = device if torch.cuda.is_available() else 'cpu'
        self.cache_dir = cache_dir or os.path.expanduser("~/.cache/huggingface")

        # Load model and tokenizer lazily (on first use)
        self._model = None
        self._tokenizer = None
        self._pipeline = None

    def _load_model(self):
        """Load translation model and tokenizer."""
        if self._model is None:
            print(f"Loading translation model: {self.model_name}...")

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )

            self._model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir
            )

            # Move model to device
            self._model.to(self.device)

            print(f"Translation model loaded on {self.device}")

    def translate(
        self,
        text: str,
        source_lang: str = "eng",
        target_lang: str = "eng",
        max_length: int = 512
    ) -> str:
        """
        Translate text from source language to target language.

        Args:
            text: Text to translate
            source_lang: Source language code (ISO 639-3)
            target_lang: Target language code (ISO 639-3)
            max_length: Maximum length of generated translation

        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""

        # If source and target are the same, return original
        if source_lang == target_lang:
            return text

        # Load model if not loaded
        self._load_model()

        # Map language codes to NLLB format
        src_lang_code = self.LANG_MAP.get(source_lang, f"{source_lang}_Latn")
        tgt_lang_code = self.LANG_MAP.get(target_lang, f"{target_lang}_Latn")

        try:
            # Set source language for tokenizer
            self._tokenizer.src_lang = src_lang_code

            # Tokenize input
            inputs = self._tokenizer(
                text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=max_length
            ).to(self.device)

            # Generate translation
            # Set target language by passing forced_bos_token_id
            forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(tgt_lang_code)

            translated_tokens = self._model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_length=max_length,
                num_beams=5,
                early_stopping=True
            )

            # Decode translation
            translation = self._tokenizer.batch_decode(
                translated_tokens,
                skip_special_tokens=True
            )[0]

            return translation

        except Exception as e:
            print(f"Translation error: {str(e)}")
            # Return original text if translation fails
            return text

    def translate_batch(
        self,
        texts: List[str],
        source_lang: str = "eng",
        target_lang: str = "eng",
        batch_size: int = 8,
        max_length: int = 512
    ) -> List[str]:
        """
        Translate multiple texts in batch.

        Args:
            texts: List of texts to translate
            source_lang: Source language code (ISO 639-3)
            target_lang: Target language code (ISO 639-3)
            batch_size: Batch size for processing
            max_length: Maximum length of generated translation

        Returns:
            List of translated texts
        """
        if not texts:
            return []

        # If source and target are the same, return originals
        if source_lang == target_lang:
            return texts

        # Load model if not loaded
        self._load_model()

        # Map language codes
        src_lang_code = self.LANG_MAP.get(source_lang, f"{source_lang}_Latn")
        tgt_lang_code = self.LANG_MAP.get(target_lang, f"{target_lang}_Latn")

        translations = []

        try:
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                # Filter out empty texts
                non_empty_batch = [(idx, text) for idx, text in enumerate(batch) if text.strip()]

                if not non_empty_batch:
                    # All empty, return empty strings
                    translations.extend([''] * len(batch))
                    continue

                indices, batch_texts = zip(*non_empty_batch)

                # Set source language
                self._tokenizer.src_lang = src_lang_code

                # Tokenize batch
                inputs = self._tokenizer(
                    list(batch_texts),
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=max_length
                ).to(self.device)

                # Generate translations
                forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(tgt_lang_code)

                translated_tokens = self._model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=max_length,
                    num_beams=5,
                    early_stopping=True
                )

                # Decode translations
                batch_translations = self._tokenizer.batch_decode(
                    translated_tokens,
                    skip_special_tokens=True
                )

                # Reconstruct full batch with empty strings where needed
                full_batch_translations = [''] * len(batch)
                for idx, translation in zip(indices, batch_translations):
                    full_batch_translations[idx] = translation

                translations.extend(full_batch_translations)

        except Exception as e:
            print(f"Batch translation error: {str(e)}")
            # Return original texts if translation fails
            return texts

        return translations

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Get list of supported languages.

        Returns:
            List of dicts with language code and name
        """
        languages = [
            {"code": "eng", "name": "English"},
            {"code": "spa", "name": "Spanish"},
            {"code": "fra", "name": "French"},
            {"code": "deu", "name": "German"},
            {"code": "ita", "name": "Italian"},
            {"code": "por", "name": "Portuguese"},
            {"code": "rus", "name": "Russian"},
            {"code": "jpn", "name": "Japanese"},
            {"code": "kor", "name": "Korean"},
            {"code": "zho", "name": "Chinese"},
            {"code": "ara", "name": "Arabic"},
            {"code": "hin", "name": "Hindi"},
            {"code": "tur", "name": "Turkish"},
            {"code": "vie", "name": "Vietnamese"},
            {"code": "pol", "name": "Polish"},
            {"code": "nld", "name": "Dutch"},
            {"code": "swe", "name": "Swedish"},
            {"code": "ind", "name": "Indonesian"},
            {"code": "tha", "name": "Thai"},
            {"code": "ukr", "name": "Ukrainian"},
        ]
        return languages

    @staticmethod
    def get_language_name(code: str) -> str:
        """Get language name from code."""
        lang_names = {
            "eng": "English",
            "spa": "Spanish",
            "fra": "French",
            "deu": "German",
            "ita": "Italian",
            "por": "Portuguese",
            "rus": "Russian",
            "jpn": "Japanese",
            "kor": "Korean",
            "zho": "Chinese",
            "ara": "Arabic",
            "hin": "Hindi",
            "tur": "Turkish",
            "vie": "Vietnamese",
            "pol": "Polish",
            "nld": "Dutch",
            "swe": "Swedish",
            "ind": "Indonesian",
            "tha": "Thai",
            "ukr": "Ukrainian",
        }
        return lang_names.get(code, code.upper())
