"""Language detection service for transcribed text."""

from typing import Dict, Optional
import re

try:
    from langdetect import detect, DetectorFactory
    # Set seed for consistent results
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False


class LanguageDetector:
    """
    Language detection service for transcribed text.

    Detects language from text using langdetect library.
    Maps detected languages to ISO 639-3 codes for consistency.
    """

    # Language code mapping (ISO 639-1 to ISO 639-3)
    LANG_MAP_639_1_TO_639_3 = {
        'en': 'eng',  # English
        'es': 'spa',  # Spanish
        'fr': 'fra',  # French
        'de': 'deu',  # German
        'it': 'ita',  # Italian
        'pt': 'por',  # Portuguese
        'ru': 'rus',  # Russian
        'ja': 'jpn',  # Japanese
        'ko': 'kor',  # Korean
        'zh-cn': 'zho',  # Chinese (Simplified)
        'zh-tw': 'zho',  # Chinese (Traditional)
        'ar': 'ara',  # Arabic
        'hi': 'hin',  # Hindi
        'tr': 'tur',  # Turkish
        'vi': 'vie',  # Vietnamese
        'pl': 'pol',  # Polish
        'nl': 'nld',  # Dutch
        'sv': 'swe',  # Swedish
        'id': 'ind',  # Indonesian
        'th': 'tha',  # Thai
        'uk': 'ukr',  # Ukrainian
        'cs': 'ces',  # Czech
        'da': 'dan',  # Danish
        'fi': 'fin',  # Finnish
        'el': 'ell',  # Greek
        'he': 'heb',  # Hebrew
        'hu': 'hun',  # Hungarian
        'no': 'nor',  # Norwegian
        'ro': 'ron',  # Romanian
        'sk': 'slk',  # Slovak
        'bg': 'bul',  # Bulgarian
        'hr': 'hrv',  # Croatian
        'sr': 'srp',  # Serbian
        'ca': 'cat',  # Catalan
        'lt': 'lit',  # Lithuanian
        'lv': 'lav',  # Latvian
        'et': 'est',  # Estonian
        'sl': 'slv',  # Slovenian
        'fa': 'fas',  # Persian
        'ur': 'urd',  # Urdu
        'bn': 'ben',  # Bengali
        'ta': 'tam',  # Tamil
        'te': 'tel',  # Telugu
        'mr': 'mar',  # Marathi
        'gu': 'guj',  # Gujarati
        'kn': 'kan',  # Kannada
        'ml': 'mal',  # Malayalam
        'pa': 'pan',  # Punjabi
        'sw': 'swa',  # Swahili
        'af': 'afr',  # Afrikaans
    }

    # Language names
    LANG_NAMES = {
        'eng': 'English',
        'spa': 'Spanish',
        'fra': 'French',
        'deu': 'German',
        'ita': 'Italian',
        'por': 'Portuguese',
        'rus': 'Russian',
        'jpn': 'Japanese',
        'kor': 'Korean',
        'zho': 'Chinese',
        'ara': 'Arabic',
        'hin': 'Hindi',
        'tur': 'Turkish',
        'vie': 'Vietnamese',
        'pol': 'Polish',
        'nld': 'Dutch',
        'swe': 'Swedish',
        'ind': 'Indonesian',
        'tha': 'Thai',
        'ukr': 'Ukrainian',
    }

    @staticmethod
    def detect_language(text: str) -> Dict[str, any]:
        """
        Detect language from text.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with language_code (ISO 639-3), language_name, and confidence
        """
        if not text or not text.strip():
            # Default to English if no text
            return {
                'language_code': 'eng',
                'language_name': 'English',
                'confidence': 0.5
            }

        # Check if langdetect is available
        if not LANGDETECT_AVAILABLE:
            # Fallback: simple character-based detection
            return LanguageDetector._fallback_detect(text)

        try:
            # Clean text for better detection
            clean_text = text.strip()

            # Detect language using langdetect
            detected = detect(clean_text)

            # Map to ISO 639-3
            lang_code_639_3 = LanguageDetector.LANG_MAP_639_1_TO_639_3.get(detected, 'eng')
            lang_name = LanguageDetector.LANG_NAMES.get(lang_code_639_3, 'English')

            return {
                'language_code': lang_code_639_3,
                'language_name': lang_name,
                'confidence': 0.95  # langdetect doesn't provide confidence scores
            }

        except Exception as e:
            print(f"Language detection error: {str(e)}")
            # Fallback to character-based detection
            return LanguageDetector._fallback_detect(text)

    @staticmethod
    def _fallback_detect(text: str) -> Dict[str, any]:
        """
        Fallback language detection based on character analysis.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with language_code, language_name, and confidence
        """
        # Count character types
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', text))
        korean_chars = len(re.findall(r'[\uac00-\ud7af]', text))
        arabic_chars = len(re.findall(r'[\u0600-\u06ff]', text))
        cyrillic_chars = len(re.findall(r'[\u0400-\u04ff]', text))
        thai_chars = len(re.findall(r'[\u0e00-\u0e7f]', text))

        total_chars = len(text.replace(' ', ''))

        if total_chars == 0:
            return {
                'language_code': 'eng',
                'language_name': 'English',
                'confidence': 0.5
            }

        # Determine language based on character distribution
        if chinese_chars / total_chars > 0.3:
            return {
                'language_code': 'zho',
                'language_name': 'Chinese',
                'confidence': 0.85
            }
        elif japanese_chars / total_chars > 0.3:
            return {
                'language_code': 'jpn',
                'language_name': 'Japanese',
                'confidence': 0.85
            }
        elif korean_chars / total_chars > 0.3:
            return {
                'language_code': 'kor',
                'language_name': 'Korean',
                'confidence': 0.85
            }
        elif arabic_chars / total_chars > 0.3:
            return {
                'language_code': 'ara',
                'language_name': 'Arabic',
                'confidence': 0.85
            }
        elif cyrillic_chars / total_chars > 0.3:
            return {
                'language_code': 'rus',
                'language_name': 'Russian',
                'confidence': 0.80
            }
        elif thai_chars / total_chars > 0.3:
            return {
                'language_code': 'tha',
                'language_name': 'Thai',
                'confidence': 0.85
            }
        else:
            # Default to English
            return {
                'language_code': 'eng',
                'language_name': 'English',
                'confidence': 0.70
            }

    @staticmethod
    def get_language_name(code: str) -> str:
        """Get language name from ISO 639-3 code."""
        return LanguageDetector.LANG_NAMES.get(code, code.upper())
